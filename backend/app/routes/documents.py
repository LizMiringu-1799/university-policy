import os

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt

from app.models.document import Document, DocumentVersion
from app.utils.errors import ApiError

documents_bp = Blueprint("documents", __name__, url_prefix="/api/v1/documents")


def _base_query():
    query = Document.query
    if get_jwt().get("role") != "admin":
        query = query.filter_by(status="active")
    return query


@documents_bp.get("")
@jwt_required()
def list_documents():
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
    rows = Document.query.filter_by(status="active").with_entities(Document.category).distinct().all()
    return jsonify({"categories": sorted({row[0] for row in rows})})


@documents_bp.get("/<int:document_id>")
@jwt_required()
def get_document(document_id):
    document = _base_query().filter_by(id=document_id).first()
    if not document:
        raise ApiError("not_found", f"document {document_id} does not exist", 404)
    return jsonify(document.to_detail_dict())


@documents_bp.get("/<int:document_id>/file")
@jwt_required()
def get_document_file(document_id):
    document = _base_query().filter_by(id=document_id).first()
    if not document:
        raise ApiError("not_found", f"document {document_id} does not exist", 404)

    version_number = request.args.get("version", type=int)
    if version_number:
        version = DocumentVersion.query.filter_by(document_id=document_id, version_number=version_number).first()
    else:
        version = document.current_version

    if not version or not os.path.exists(version.file_path):
        raise ApiError("not_found", "file not found for this document/version", 404)

    return send_file(version.file_path, mimetype="application/pdf", conditional=True, as_attachment=False)
