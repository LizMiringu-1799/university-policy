from flask import Blueprint, request, jsonify

from app.models.query_log import Feedback, QueryLog
from app.utils.auth import role_required
from app.utils.errors import ApiError

admin_ratings_bp = Blueprint("admin_ratings", __name__, url_prefix="/api/v1/admin/ratings")

RATINGS = ("up", "down")


def _rating_dict(feedback):
    """One rated answer, with the question/answer it belongs to: the whole point of
    this view is showing what a thumbs down was actually about, not just the number.
    Distinct from Escalation.to_dict()'s embedded `rating`, which is the same feedback
    row seen from the other direction (via the escalation it happens to be attached to,
    if any) — this is every rating, escalated or not."""
    log = feedback.query_log
    return {
        "id": feedback.id,
        "rating": feedback.rating,
        "comment": feedback.comment,
        "created_at": feedback.created_at.isoformat() + "Z" if feedback.created_at else None,
        "updated_at": feedback.updated_at.isoformat() + "Z" if feedback.updated_at else None,
        "student": {"id": feedback.user.id, "name": feedback.user.name} if feedback.user else None,
        "query": {
            "id": log.id,
            "question": log.query_text,
            "answer_md": log.answer_text,
            "confidence": log.confidence,
            "document": {"id": log.document.id, "title": log.document.title} if log.document else None,
            "created_at": log.created_at.isoformat() + "Z" if log.created_at else None,
        }
        if log
        else None,
    }


@admin_ratings_bp.get("")
@role_required("admin")
def list_ratings():
    """Every student/staff rating on a system answer, newest first — independent of
    whether that question was ever escalated (AdminEscalationsPage only shows a rating
    when it happens to sit on an escalated question, which is the minority: most rated
    answers were never escalated at all). `?rating=up|down` filters; `counts` in the
    response is the up/down split across the *unfiltered* set, for a page-header summary
    that doesn't change as the admin flips the filter."""
    rating = request.args.get("rating")
    if rating and rating not in RATINGS:
        raise ApiError("validation_error", f"rating must be one of {RATINGS}", 400)

    counts = {value: Feedback.query.filter_by(rating=value).count() for value in RATINGS}

    query = Feedback.query
    if rating:
        query = query.filter_by(rating=rating)

    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

    # id as a tiebreaker: created_at has second resolution.
    pagination = query.order_by(Feedback.created_at.desc(), Feedback.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify(
        {
            "items": [_rating_dict(f) for f in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "counts": counts,
        }
    )
