import os

from flask import Blueprint, current_app, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt

from app.models.document import Document, DocumentVersion
from app.rag.extraction import ExtractionError, extract_pages
from app.utils import filetypes
from app.utils.errors import ApiError

documents_bp = Blueprint("documents", __name__, url_prefix="/api/v1/documents")


def _base_query():
    """Document.query, restricted to active documents for non-admins. Every read route
    below starts from this so archived policies stay invisible to students by default."""
    query = Document.query
    if get_jwt().get("role") != "admin":
        query = query.filter_by(status="active")
    return query


@documents_bp.get("")
@jwt_required()
def list_documents():
    """Paginated, filterable document list (the policy library and the admin table).
    Supports title search (`q`), `category`, and — admin only — `status`."""
    query = _base_query()

    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(Document.title.ilike(f"%{q}%"))

    category = request.args.get("category", "").strip()
    if category:
        query = query.filter_by(category=category)

    if get_jwt().get("role") == "admin":
        status = request.args.get("status", "").strip()
        if status:
            query = query.filter_by(status=status)

    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

    pagination = query.order_by(Document.updated_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [doc.to_summary_dict() for doc in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
        }
    )


@documents_bp.get("/categories")
@jwt_required()
def list_categories():
    """Distinct categories across active documents, for the library's filter dropdown."""
    rows = Document.query.filter_by(status="active").with_entities(Document.category).distinct().all()
    return jsonify({"categories": sorted({row[0] for row in rows})})


@documents_bp.get("/<int:document_id>")
@jwt_required()
def get_document(document_id):
    """One document's full detail, including its version history."""
    document = _base_query().filter_by(id=document_id).first()
    if not document:
        raise ApiError("not_found", f"document {document_id} does not exist", 404)
    return jsonify(document.to_detail_dict())


def _resolve_version(document, version_number):
    """The document's version matching `version_number`, or its current version when
    `version_number` is falsy. Shared by /file and /text so both honor ?version=N the
    same way."""
    if version_number:
        return DocumentVersion.query.filter_by(document_id=document.id, version_number=version_number).first()
    return document.current_version


@documents_bp.get("/<int:document_id>/file")
@jwt_required()
def get_document_file(document_id):
    """Stream the file itself, for the in-browser reader (PDFs and images go straight
    into a native viewer there; Word/text documents use /text instead, see below).
    `?version=N` fetches an old version instead of the current one; `conditional=True`
    lets the browser range-request and cache it rather than re-downloading the whole
    file on every page jump."""
    document = _base_query().filter_by(id=document_id).first()
    if not document:
        raise ApiError("not_found", f"document {document_id} does not exist", 404)

    version = _resolve_version(document, request.args.get("version", type=int))
    if not version or not os.path.exists(version.file_path):
        raise ApiError("not_found", "file not found for this document/version", 404)

    media_type = filetypes.media_type_for(version.file_type, version.file_path)
    return send_file(version.file_path, mimetype=media_type, conditional=True, as_attachment=False)


@documents_bp.get("/<int:document_id>/text")
@jwt_required()
def get_document_text(document_id):
    """Extracted text, paginated the same way indexing sees it, for formats the browser
    can't render natively (Word docs, plain text — filetypes.viewer_for == "text").
    `?version=N` behaves as in /file.

    Runs extraction synchronously with OCR off, which is safe here only because neither
    format this route serves ever needs OCR (both are born-digital); a scanned PDF or
    image is rejected with 409 rather than risk running OCR inline on a web request.
    """
    document = _base_query().filter_by(id=document_id).first()
    if not document:
        raise ApiError("not_found", f"document {document_id} does not exist", 404)

    version = _resolve_version(document, request.args.get("version", type=int))
    if not version or not os.path.exists(version.file_path):
        raise ApiError("not_found", "file not found for this document/version", 404)

    if filetypes.viewer_for(version.file_type) != "text":
        raise ApiError("conflict", "this document's viewer is not text-based; use /file instead", 409)

    try:
        pages = extract_pages(
            version.file_path,
            version.file_type,
            min_chars_per_page=0,
            page_chars=current_app.config["RAG_PAGE_CHARS"],
            ocr_enabled=False,
        )
    except ExtractionError as err:
        raise ApiError("upstream_error", f"could not read this document: {err}", 502)

    return jsonify({"file_type": version.file_type, "pages": [{"page": n, "text": t} for n, t in pages]})
