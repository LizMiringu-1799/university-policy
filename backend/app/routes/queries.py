from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.models.document import Document
from app.rag.answer import AnswerError, AnswerRateLimited, answer_question
from app.utils.errors import ApiError

queries_bp = Blueprint("queries", __name__, url_prefix="/api/v1")


@queries_bp.post("/ask")
@jwt_required()
def ask():
    data = request.get_json(silent=True) or {}

    question = (data.get("question") or "").strip()
    if not question:
        raise ApiError("validation_error", "question is required", 400)
    if len(question) > 1000:
        raise ApiError("validation_error", "question must be at most 1000 characters", 400)

    # Optional: scope the search to one policy, which is what the reader page's panel does.
    document_id = data.get("document_id")
    if document_id is not None:
        if not isinstance(document_id, int):
            raise ApiError("validation_error", "document_id must be an integer", 400)
        document = Document.query.filter_by(id=document_id, status="active").first()
        if not document:
            raise ApiError("not_found", f"document {document_id} is not available", 404)

    try:
        result = answer_question(question, document_id=document_id)
    except AnswerRateLimited:
        raise ApiError(
            "rate_limited",
            "the answering service is busy right now; try again in a moment",
            429,
        )
    except AnswerError:
        raise ApiError("upstream_error", "the answering service could not be reached", 502)

    return jsonify(result)
