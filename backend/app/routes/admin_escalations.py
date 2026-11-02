from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.models.escalation import Escalation
from app.utils.auth import role_required
from app.utils.errors import ApiError

admin_escalations_bp = Blueprint("admin_escalations", __name__, url_prefix="/api/v1/admin/escalations")


REASONS = ("unanswered", "clarification")


@admin_escalations_bp.get("")
@role_required("admin")
def list_escalations():
    """The admin queue of student questions. `?status=open|resolved` filters; omitted
    returns everything, open first. `?reason=unanswered|clarification` separates the two
    kinds of question this queue mixes — one the system raised on its own because it
    couldn't answer, one a student raised by asking for more detail on an answer it did
    give — so the admin UI can show them as separate tabs rather than one blended list."""
    status = request.args.get("status")
    reason = request.args.get("reason")
    query = Escalation.query
    if status:
        if status not in ("open", "resolved"):
            raise ApiError("validation_error", "status must be 'open' or 'resolved'", 400)
        query = query.filter_by(status=status)
    if reason:
        if reason not in REASONS:
            raise ApiError("validation_error", f"reason must be one of {REASONS}", 400)
        query = query.filter_by(reason=reason)

    # Open ones first and oldest-first within that, so the admin works through the queue
    # in the order students have been waiting; resolved ones trail behind for reference.
    # id as a tiebreaker for two escalations raised in the same second.
    items = query.order_by(
        Escalation.status.desc(), Escalation.created_at.asc(), Escalation.id.asc()
    ).all()
    return jsonify({"items": [e.to_dict() for e in items]})


@admin_escalations_bp.get("/open-count")
@role_required("admin")
def open_count():
    """Cheap count for a badge, so it doesn't have to pull every open question's
    question/answer text just to show a number. `?reason=` scopes it to one of the two
    queues (AdminEscalationsPage's tab badges); omitted, it's the aggregate the header
    badge shows."""
    reason = request.args.get("reason")
    query = Escalation.query.filter_by(status="open")
    if reason:
        if reason not in REASONS:
            raise ApiError("validation_error", f"reason must be one of {REASONS}", 400)
        query = query.filter_by(reason=reason)
    return jsonify({"count": query.count()})


@admin_escalations_bp.post("/<int:escalation_id>/respond")
@role_required("admin")
def respond(escalation_id):
    """Record an admin's reply to one escalation and close it out.

    Body: {admin_response}. Marks the escalation resolved and stamps who answered and
    when, so the student's "My Questions" page can show both the reply and its provenance."""
    escalation = Escalation.query.get(escalation_id)
    if not escalation:
        raise ApiError("not_found", f"escalation {escalation_id} does not exist", 404)

    data = request.get_json(silent=True) or {}
    admin_response = (data.get("admin_response") or "").strip()
    if not admin_response:
        raise ApiError("validation_error", "admin_response is required", 400)
    if len(admin_response) > 4000:
        raise ApiError("validation_error", "admin_response must be at most 4000 characters", 400)

    escalation.admin_response = admin_response
    escalation.status = "resolved"
    escalation.resolved_by = int(get_jwt_identity())
    escalation.resolved_at = datetime.utcnow()
    db.session.commit()

    return jsonify(escalation.to_dict())
