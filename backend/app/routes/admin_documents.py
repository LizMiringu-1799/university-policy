from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.models.document import Document, DocumentVersion
from app.rag import ingest, store
from app.utils.auth import role_required
from app.utils.errors import ApiError
from app.utils.storage import validate_pdf_upload, save_pdf_version

admin_documents_bp = Blueprint("admin_documents", __name__, url_prefix="/api/v1/admin/documents")


@admin_documents_bp.post("")
@role_required("admin")
def create_document():
    title = (request.form.get("title") or "").strip()
    category = (request.form.get("category") or "").strip()
    if not title or len(title) > 200:
        raise ApiError("validation_error", "title is required and must be at most 200 characters", 400)
    if not category or len(category) > 100:
        raise ApiError("validation_error", "category is required and must be at most 100 characters", 400)

    file_storage = request.files.get("file")
    validate_pdf_upload(file_storage)

    user_id = int(get_jwt_identity())
    document = Document(title=title, category=category, created_by=user_id)
    db.session.add(document)
    db.session.flush()  # assigns document.id without committing

    file_path, file_sha256, page_count = save_pdf_version(file_storage, document.id, version_number=1)
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_path=file_path,
        file_sha256=file_sha256,
        page_count=page_count,
        uploaded_by=user_id,
    )
    db.session.add(version)
    db.session.flush()

    document.current_version_id = version.id
    db.session.commit()

    ingest.enqueue(version)

    return jsonify(document.to_detail_dict()), 201


@admin_documents_bp.post("/<int:document_id>/versions")
@role_required("admin")
def add_version(document_id):
    document = Document.query.get(document_id)
    if not document:
        raise ApiError("not_found", f"document {document_id} does not exist", 404)

    file_storage = request.files.get("file")
    validate_pdf_upload(file_storage)

    user_id = int(get_jwt_identity())
    next_version_number = (document.current_version.version_number if document.current_version else 0) + 1

    file_path, file_sha256, page_count = save_pdf_version(file_storage, document.id, next_version_number)
    version = DocumentVersion(
        document_id=document.id,
        version_number=next_version_number,
        file_path=file_path,
        file_sha256=file_sha256,
        page_count=page_count,
        uploaded_by=user_id,
    )
    db.session.add(version)
    db.session.flush()

    document.current_version_id = version.id
    db.session.commit()

    # The superseded version's chunks are dropped by the worker once the new ones are in,
    # so the document stays answerable at its old version until the new one is ready.
    ingest.enqueue(version)

    return jsonify(document.to_detail_dict()), 201


@admin_documents_bp.patch("/<int:document_id>")
@role_required("admin")
def update_document(document_id):
    document = Document.query.get(document_id)
    if not document:
        raise ApiError("not_found", f"document {document_id} does not exist", 404)

    data = request.get_json(silent=True) or {}
    previous_status = document.status
    embedded_text_changed = False

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title or len(title) > 200:
            raise ApiError("validation_error", "title must be 1-200 characters", 400)
        # The title is prefixed onto every chunk before embedding, so changing it
        # invalidates this document's vectors (docs/design-rag.md §3).
        embedded_text_changed = embedded_text_changed or title != document.title
        document.title = title

    if "category" in data:
        category = (data["category"] or "").strip()
        if not category or len(category) > 100:
            raise ApiError("validation_error", "category must be 1-100 characters", 400)
        embedded_text_changed = embedded_text_changed or category != document.category
        document.category = category

    if "status" in data:
        if data["status"] not in ("active", "archived"):
            raise ApiError("validation_error", "status must be 'active' or 'archived'", 400)
        document.status = data["status"]

    # Archiving drops the chunks before the status is committed: if Chroma refuses, the
    # archive fails loudly rather than leaving a hidden policy still answerable. The lock
    # keeps an in-flight indexing job from writing the chunks back afterwards.
    archiving = previous_status == "active" and document.status == "archived"
    if archiving:
        with store.index_lock:
            store.delete_document(document.id)
            try:
                db.session.commit()
            except Exception:
                current_app.logger.error(
                    "Archiving document %s failed after its chunks were removed. It is still "
                    "active but unsearchable; use Reindex to restore it.",
                    document.id,
                )
                raise
    else:
        db.session.commit()

    restoring = previous_status == "archived" and document.status == "active"
    if restoring or (embedded_text_changed and document.status == "active"):
        ingest.enqueue_current(document)

    return jsonify(document.to_detail_dict())


@admin_documents_bp.get("/<int:document_id>/index-status")
@role_required("admin")
def get_index_status(document_id):
    document = Document.query.get(document_id)
    if not document:
        raise ApiError("not_found", f"document {document_id} does not exist", 404)

    version = document.current_version
    if not version:
        raise ApiError("not_found", f"document {document_id} has no current version", 404)

    return jsonify(
        {
            "version_id": version.id,
            "version_number": version.version_number,
            "index_status": version.index_status,
            "chunk_count": version.chunk_count,
            "index_error": version.index_error,
        }
    )


@admin_documents_bp.post("/<int:document_id>/reindex")
@role_required("admin")
def reindex_document(document_id):
    document = Document.query.get(document_id)
    if not document:
        raise ApiError("not_found", f"document {document_id} does not exist", 404)
    if document.status != "active":
        raise ApiError("conflict", "restore the document before reindexing it", 409)

    version = document.current_version
    if not version:
        raise ApiError("not_found", f"document {document_id} has no current version", 404)

    ingest.enqueue(version)
    return jsonify({"version_id": version.id, "index_status": version.index_status}), 202
