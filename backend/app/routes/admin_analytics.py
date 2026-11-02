from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import Integer, cast, func

from app.extensions import db
from app.models.document import Document
from app.models.query_log import QueryLog, QueryRetrieval
from app.utils.auth import role_required
from app.utils.errors import ApiError

admin_analytics_bp = Blueprint("admin_analytics", __name__, url_prefix="/api/v1/admin/analytics")

# A document retrieved only once or twice hasn't earned a verdict either way — one
# unlucky low-similarity match shouldn't rank a policy as "ambiguous". Filters the
# /ambiguous ranking, not /documents (which reports everything, unfiltered, as demand).
AMBIGUOUS_MIN_RETRIEVED = 2

# How many example questions /ambiguous attaches per document.
SAMPLE_QUERIES_PER_DOCUMENT = 3


def _parse_date(value, field_name):
    """One ?from=/?to= query param (YYYY-MM-DD) as a date, or None if absent."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ApiError("validation_error", f"{field_name} must be an ISO date (YYYY-MM-DD)", 400)


def _date_range_filter(query, column):
    """Apply ?from=/?to= to `query`, filtering `column` (a DateTime column) to the
    inclusive day range `to` names — up to the end of that day, not just its midnight."""
    from_date = _parse_date(request.args.get("from"), "from")
    to_date = _parse_date(request.args.get("to"), "to")
    if from_date:
        query = query.filter(column >= from_date)
    if to_date:
        query = query.filter(column < to_date + timedelta(days=1))
    return query


@admin_analytics_bp.get("/summary")
@role_required("admin")
def summary():
    """Headline pilot numbers: volume, outcome mix, and quality signals, plus a
    day-by-day series for the volume-over-time chart. `?from=&to=` (YYYY-MM-DD) scope
    the window; omitted, it's all logged history."""
    base = _date_range_filter(QueryLog.query, QueryLog.created_at)

    total_queries = base.count()
    distinct_users = base.with_entities(QueryLog.user_id).distinct().count()

    status_counts = dict(
        base.with_entities(QueryLog.status, func.count(QueryLog.id)).group_by(QueryLog.status).all()
    )

    avg_confidence = base.with_entities(func.avg(QueryLog.confidence)).scalar()
    avg_response_ms = base.with_entities(func.avg(QueryLog.response_ms)).scalar()

    per_day = (
        base.with_entities(func.date(QueryLog.created_at).label("day"), func.count(QueryLog.id))
        .group_by("day")
        .order_by("day")
        .all()
    )

    return jsonify(
        {
            "total_queries": total_queries,
            "distinct_users": distinct_users,
            "answered": status_counts.get("answered", 0),
            "unanswered": status_counts.get("unanswered", 0),
            "error": status_counts.get("error", 0),
            "avg_confidence": round(float(avg_confidence), 4) if avg_confidence is not None else None,
            "avg_response_ms": round(float(avg_response_ms)) if avg_response_ms is not None else None,
            "queries_per_day": [
                {"date": day.isoformat() if hasattr(day, "isoformat") else str(day), "count": count}
                for day, count in per_day
            ],
        }
    )


def _document_aggregates():
    """Per-document retrieval stats from query_retrievals: how often the retriever
    surfaced each policy's chunks, how often that paid off in a citation, and how strong
    the matches were on average. Shared by /documents and /ambiguous, which rank and
    filter this same base differently rather than re-querying it."""
    rows = (
        db.session.query(
            QueryRetrieval.document_id,
            func.count(QueryRetrieval.id),
            # Cast before summing: func.sum() on a Boolean column inherits Boolean as
            # its own result type, so SQLAlchemy coerces the integer total (e.g. 3) back
            # to a bare True/False before it ever reaches Python. The cast to Integer
            # keeps the real count.
            func.sum(cast(QueryRetrieval.cited, Integer)),
            func.avg(QueryRetrieval.similarity),
        )
        .group_by(QueryRetrieval.document_id)
        .all()
    )
    titles = dict(Document.query.with_entities(Document.id, Document.title).all())

    stats = []
    for document_id, times_retrieved, times_cited, avg_similarity in rows:
        stats.append(
            {
                "document_id": document_id,
                # A document can be deleted (hard-deleted test data, not the normal
                # archive path) after queries already cite its retrievals; fall back
                # rather than let a stale FK 500 the whole endpoint.
                "title": titles.get(document_id, "(deleted document)"),
                "times_retrieved": times_retrieved,
                "times_cited": int(times_cited or 0),
                "avg_similarity": round(float(avg_similarity), 4) if avg_similarity is not None else None,
            }
        )
    return stats


def _unanswered_counts():
    """{document_id: count of distinct unanswered queries that retrieved it}. A query
    counts once per document no matter how many of that document's chunks it retrieved."""
    rows = (
        db.session.query(QueryRetrieval.document_id, func.count(func.distinct(QueryRetrieval.query_log_id)))
        .join(QueryLog, QueryLog.id == QueryRetrieval.query_log_id)
        .filter(QueryLog.status == "unanswered")
        .group_by(QueryRetrieval.document_id)
        .all()
    )
    return dict(rows)


def _sample_queries(document_id, limit=SAMPLE_QUERIES_PER_DOCUMENT):
    """A few example questions that retrieved `document_id`, unanswered ones first —
    those are the actionable examples for an admin reading the ambiguity list, since an
    answered query that happened to retrieve this document alongside others isn't
    evidence of anything wrong with it."""

    def base_query():
        return (
            db.session.query(QueryLog.query_text)
            .join(QueryRetrieval, QueryRetrieval.query_log_id == QueryLog.id)
            .filter(QueryRetrieval.document_id == document_id)
        )

    unanswered = (
        base_query()
        .filter(QueryLog.status == "unanswered")
        .order_by(QueryLog.created_at.desc())
        .distinct()
        .limit(limit)
        .all()
    )
    samples = [row[0] for row in unanswered]

    remaining = limit - len(samples)
    if remaining > 0:
        query = base_query().order_by(QueryLog.created_at.desc()).distinct()
        if samples:
            query = query.filter(~QueryLog.query_text.in_(samples))
        samples += [row[0] for row in query.limit(remaining).all()]

    return samples


@admin_analytics_bp.get("/documents")
@role_required("admin")
def documents():
    """Retrieval demand per document: how often each policy's chunks were offered to the
    model, and how often that paid off in an actual citation. Sorted most-retrieved
    first — the dashboard's "most-queried policies" chart."""
    stats = _document_aggregates()
    stats.sort(key=lambda s: s["times_retrieved"], reverse=True)
    return jsonify(stats)


@admin_analytics_bp.get("/ambiguous")
@role_required("admin")
def ambiguous():
    """Policies the retriever keeps surfacing but the model keeps finding unhelpful:
    retrieved often, cited rarely, with weak average similarity — the signal that a
    policy is missing, poorly worded, or genuinely ambiguous (design-rag.md §4.4, which
    explains why this reads retrievals rather than confidence: an unanswered query cites
    nothing and so has no confidence signal at all, which is exactly the case this metric
    exists to catch).

    Ranked by retrieved-but-not-cited *count*, not `cite_rate` alone — a document
    retrieved twice and cited once (50%) is noise next to one retrieved 40 times and
    cited 4 times (90% ignored); the raw count of ignored retrievals is what actually
    says "this keeps confusing the system." Ties broken by weaker average similarity.
    `?limit=20` (max 100)."""
    limit = request.args.get("limit", 20, type=int)
    if limit < 1:
        raise ApiError("validation_error", "limit must be at least 1", 400)
    limit = min(limit, 100)

    candidates = [s for s in _document_aggregates() if s["times_retrieved"] >= AMBIGUOUS_MIN_RETRIEVED]
    unanswered_counts = _unanswered_counts()

    ranked = sorted(
        candidates,
        key=lambda s: (
            -(s["times_retrieved"] - s["times_cited"]),
            s["avg_similarity"] if s["avg_similarity"] is not None else 1.0,
        ),
    )[:limit]

    return jsonify(
        [
            {
                "document_id": s["document_id"],
                "title": s["title"],
                "times_retrieved": s["times_retrieved"],
                "times_cited": s["times_cited"],
                "cite_rate": round(s["times_cited"] / s["times_retrieved"], 4),
                "mean_similarity": s["avg_similarity"],
                "unanswered_queries": unanswered_counts.get(s["document_id"], 0),
                "sample_queries": _sample_queries(s["document_id"]),
            }
            for s in ranked
        ]
    )
