from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.models.escalation import Escalation
from app.utils.auth import role_required
from app.utils.errors import ApiError

admin_escalations_bp = Blueprint("admin_escalations", __name__, url_prefix="/api/v1/admin/escalations")


@admin_escalations_bp.get("")
@role_required("admin")
def list_escalations():
    status = request.args.get("status")
    query = Escalation.query
    if status:
        if status not in ("open", "resolved"):
            raise ApiError("validation_error", "status must be 'open' or 'resolved'", 400)
        query = query.filter_by(status=status)

    # Open ones first and oldest-first within that, so the admin works through the queue
    # in the order students have been waiting; resolved ones trail behind for reference.
    items = query.order_by(Escalation.status.desc(), Escalation.created_at.asc()).all()
    return jsonify({"items": [e.to_dict() for e in items]})


@admin_escalations_bp.get("/open-count")
@role_required("admin")
def open_count():
    """Cheap count for the header badge, so it doesn't have to pull every open
    question's question/answer text just to show a number."""
    return jsonify({"count": Escalation.query.filter_by(status="open").count()})


@admin_escalations_bp.post("/<int:escalation_id>/respond")
@role_required("admin")
def respond(escalation_id):
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
