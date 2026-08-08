import logging
import os
import threading

from flask import current_app

logger = logging.getLogger(__name__)

# ONNX Runtime sizes its thread pool to the core count, so embedding a document would
# otherwise take every core and starve the Flask threads sharing this process. Set before
# chromadb is imported, since the value is read when the runtime initialises.
os.environ.setdefault("OMP_NUM_THREADS", "1")

_client = None
_lock = threading.Lock()

# Serializes "write a version's chunks" against "remove a document's chunks", so an
# archive landing mid-ingest cannot be overwritten by the indexing job it raced. Held by
# the worker across the embedding call, which is seconds; archive requests block for that
# long only while an ingest is actually running. See docs/design-rag.md §3.
index_lock = threading.RLock()

ADD_BATCH_SIZE = 64


def _get_collection():
    """The `policies` collection, created on first use.

    Chroma's default distance is L2 and the space cannot be changed after creation, so
    cosine is pinned here and verified on every call against an existing collection.
    """
    global _client

    with _lock:
        if _client is None:
            import chromadb
            from chromadb.config import Settings

            # chromadb 0.5.23 honours anonymized_telemetry by setting posthog.disabled,
            # but still calls posthog.capture(), which fails on a positional-argument
            # mismatch and logs an error per operation. Nothing is sent either way; this
            # only mutes the noise.
            logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

            path = current_app.config["CHROMA_DIR"]
            os.makedirs(path, exist_ok=True)
            _client = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))

    collection = _client.get_or_create_collection(
        name=current_app.config["CHROMA_COLLECTION"],
        metadata={"hnsw:space": "cosine"},
    )

    space = (collection.metadata or {}).get("hnsw:space")
    if space != "cosine":
        logger.warning(
            "Chroma collection %r uses %r distance, not cosine. Similarity scores will be "
            "wrong. Delete the CHROMA_DIR and reindex to rebuild it.",
            collection.name,
            space,
        )

    return collection


def reset_client():
    """Drop the cached client so the next call reopens it. For tests and CLI teardown."""
    global _client
    with _lock:
        _client = None


def chunk_id(document_id, version_id, chunk_index):
    return f"doc{document_id}_v{version_id}_c{chunk_index}"


def delete_version(document_id, version_id):
    """Remove one version's chunks. Used to clean up a half-written index after a failure."""
    _get_collection().delete(where={"$and": [{"document_id": document_id}, {"version_id": version_id}]})


def add_chunks(document, version, chunks):
    """Write one version's chunks, replacing anything already stored for that version."""
    collection = _get_collection()
    collection.delete(where={"$and": [{"document_id": document.id}, {"version_id": version.id}]})

    for start in range(0, len(chunks), ADD_BATCH_SIZE):
        batch = chunks[start : start + ADD_BATCH_SIZE]
        collection.add(
            ids=[chunk_id(document.id, version.id, c["chunk_index"]) for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[
                {
                    "document_id": document.id,
                    "version_id": version.id,
                    "version_number": version.version_number,
                    "title": document.title,
                    "category": document.category,
                    "page": c["page"],
                    "chunk_index": c["chunk_index"],
                }
                for c in batch
            ],
        )


def delete_superseded_versions(document_id, current_version_id):
    """Drop chunks belonging to any version of this document other than the current one.

    Runs after the new version's chunks are committed, so a crash mid-ingest leaves the
    document searchable at its previous version rather than dropping out of the index.
    """
    _get_collection().delete(
        where={"$and": [{"document_id": document_id}, {"version_id": {"$ne": current_version_id}}]}
    )


def delete_document(document_id):
    """Remove a document from the index entirely. Used on archive."""
    _get_collection().delete(where={"document_id": document_id})


def query(text, k, document_id=None):
    """Nearest-neighbour search. `document_id` scopes the search to one policy.

    Used by the reader page's panel, which asks about the policy on screen rather
    than the whole corpus.
    """
    kwargs = {}
    if document_id is not None:
        kwargs["where"] = {"document_id": document_id}
    return _get_collection().query(
        query_texts=[text],
        n_results=k,
        include=["documents", "metadatas", "distances"],
        **kwargs,
    )


def count():
    return _get_collection().count()
