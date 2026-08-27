from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.document import Document
from app.models.escalation import Escalation
from app.utils.errors import ApiError

escalations_bp = Blueprint("escalations", __name__, url_prefix="/api/v1/escalations")

REASONS = ("unanswered", "clarification")


@escalations_bp.post("")
@jwt_required()
def create_escalation():
    """Hand a question to an admin. Called automatically by the client when the RAG
    pipeline can't answer, or when a student asks to follow up on an answer it gave."""
    data = request.get_json(silent=True) or {}

    question = (data.get("question") or "").strip()
    if not question:
        raise ApiError("validation_error", "question is required", 400)
    if len(question) > 1000:
        raise ApiError("validation_error", "question must be at most 1000 characters", 400)

    reason = data.get("reason")
    if reason not in REASONS:
        raise ApiError("validation_error", f"reason must be one of {REASONS}", 400)

    document_id = data.get("document_id")
    if document_id is not None:
        if not isinstance(document_id, int):
            raise ApiError("validation_error", "document_id must be an integer", 400)
        if not Document.query.get(document_id):
            raise ApiError("not_found", f"document {document_id} does not exist", 404)

    system_answer_md = data.get("system_answer_md")
    system_confidence = data.get("system_confidence")

    escalation = Escalation(
        student_id=int(get_jwt_identity()),
        document_id=document_id,
        reason=reason,
        question=question,
        system_answer_md=system_answer_md,
        system_confidence=system_confidence,
    )
    db.session.add(escalation)
    db.session.commit()

    return jsonify(escalation.to_dict()), 201


@escalations_bp.get("/mine")
@jwt_required()
def list_mine():
    """The requesting student's own escalations, newest first, so they can check back
    for the admin's reply without needing a notification system."""
    items = (
        Escalation.query.filter_by(student_id=int(get_jwt_identity()))
        .order_by(Escalation.created_at.desc())
        .all()
    )
    return jsonify({"items": [e.to_dict() for e in items]})
