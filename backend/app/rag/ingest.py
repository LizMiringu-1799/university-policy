import logging
import queue
import threading

from flask import current_app

from app.extensions import db
from app.models.document import Document, DocumentVersion
from app.rag import store
from app.rag.chunking import build_chunks
from app.rag.extraction import ExtractionError, extract_pages

logger = logging.getLogger(__name__)

_queue = queue.Queue()
_bootstrap_lock = threading.Lock()
_bootstrapped = False


def init_app(app):
    """Arm the ingestion worker, started on this process's first request.

    Deliberately lazy rather than started from the app factory. Under the Werkzeug
    reloader the app is built in both the supervisor process and the child, and only the
    child serves. Two workers against one Chroma directory corrupt the index rather than
    erroring, so the worker starts on the first request, which the supervisor never sees.
    """

    @app.before_request
    def _start_worker_once():
        if not _bootstrapped:
            _bootstrap(app)


def _bootstrap(app):
    """One-time setup, guarded by _bootstrap_lock/_bootstrapped so concurrent first
    requests only do this once: requeue anything left mid-flight, then start the worker
    thread that drains _queue for the rest of the process's life."""
    global _bootstrapped
    with _bootstrap_lock:
        if _bootstrapped:
            return
        _bootstrapped = True

    _recover_orphans(app)
    threading.Thread(target=_run, args=(app,), name="ingest-worker", daemon=True).start()


def _recover_orphans(app):
    """Requeue anything a previous process left mid-flight.

    A container or dev server killed during ingestion strands rows at `indexing` forever;
    without this they are documents that never become searchable and never say why.
    """
    with app.app_context():
        stranded = DocumentVersion.query.filter_by(index_status="indexing").all()
        for version in stranded:
            version.index_status = "pending"
        if stranded:
            db.session.commit()
            logger.info("Requeued %d version(s) stranded at 'indexing'", len(stranded))

        pending = (
            DocumentVersion.query.join(Document, Document.current_version_id == DocumentVersion.id)
            .filter(Document.status == "active", DocumentVersion.index_status == "pending")
            .all()
        )
        for version in pending:
            _queue.put(version.id)
        if pending:
            logger.info("Queued %d pending version(s) for indexing", len(pending))


def _run(app):
    """The worker thread's body: block on _queue and index one version at a time for the
    life of the process. Runs forever; ingestion is serialized this way because Chroma's
    persistent client and the CPU-bound embedding model don't tolerate concurrent writers."""
    while True:
        version_id = _queue.get()
        try:
            # One app context per item, so Flask-SQLAlchemy tears the session down between
            # jobs instead of the worker holding a MySQL connection with a stale
            # transaction open for the life of the process.
            with app.app_context():
                index_version(version_id)
        except Exception:
            logger.exception("Ingestion failed for version %s", version_id)
        finally:
            _queue.task_done()


def enqueue(version):
    """Mark a version pending and hand it to the worker."""
    version.index_status = "pending"
    version.index_error = None
    db.session.commit()
    _queue.put(version.id)


def enqueue_current(document):
    """enqueue() a document's current version, if it has one. No-op for a document with
    no versions yet (shouldn't happen in practice, but upload order isn't enforced here)."""
    if document.current_version:
        enqueue(document.current_version)


def index_version(version_id):
    """Extract, chunk, embed and store one version. Requires an app context."""
    version = DocumentVersion.query.get(version_id)
    if not version:
        return

    document = version.document
    if document.status != "active":
        logger.info("Skipping version %s: document %s is archived", version_id, document.id)
        return
    if document.current_version_id != version.id:
        logger.info("Skipping version %s: superseded by v%s", version_id, document.current_version_id)
        return

    version.index_status = "indexing"
    version.index_error = None
    db.session.commit()

    try:
        pages = extract_pages(
            version.file_path,
            version.file_type,
            min_chars_per_page=current_app.config["RAG_MIN_CHARS_PER_PAGE"],
            page_chars=current_app.config["RAG_PAGE_CHARS"],
            ocr_enabled=current_app.config["RAG_OCR_ENABLED"],
        )
        chunks = build_chunks(
            pages,
            document.title,
            current_app.config["RAG_CHUNK_CHARS"],
            current_app.config["RAG_CHUNK_MAX_CHARS"],
            current_app.config["RAG_CHUNK_OVERLAP_CHARS"],
        )
        if not chunks:
            raise ExtractionError("the PDF produced no text chunks")

        with store.index_lock:
            # Re-read under the lock: extraction and embedding take seconds, and an
            # archive or a newer upload landing in that window would otherwise be undone
            # by the write below, leaving an archived policy permanently searchable.
            db.session.refresh(document)
            if document.status != "active" or document.current_version_id != version.id:
                logger.info(
                    "Discarding index for version %s: archived or superseded during ingest", version_id
                )
                return

            store.add_chunks(document, version, chunks)
            # Only once the new chunks are stored, so a failure above leaves the document
            # searchable at its previous version rather than out of the index entirely.
            store.delete_superseded_versions(document.id, version.id)
    except ExtractionError as err:
        _mark_failed(version, str(err))
        return
    except Exception as err:
        logger.exception("Indexing version %s failed", version_id)
        # add_chunks writes in batches, so a mid-write failure can leave a partial version
        # in the index. Drop it: the previous version's chunks are still there, and a
        # truncated document answering questions is worse than one that fell back.
        try:
            store.delete_version(document.id, version.id)
        except Exception:
            logger.exception("Could not clean up partial index for version %s", version_id)
        _mark_failed(version, f"{type(err).__name__}: {err}")
        return

    version.index_status = "indexed"
    version.chunk_count = len(chunks)
    version.index_error = None
    db.session.commit()
    logger.info("Indexed document %s v%s: %d chunks", document.id, version.version_number, len(chunks))


def _mark_failed(version, message):
    """Record an ingestion failure on the version row, truncated to fit the column, and
    clear chunk_count so a stale count from a previous successful version doesn't linger."""
    version.index_status = "failed"
    version.index_error = message[:500]
    version.chunk_count = None
    db.session.commit()
