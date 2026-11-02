from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.document import Document
from app.models.query_log import Feedback, QueryLog, QueryRetrieval
from app.rag.answer import AnswerError, AnswerRateLimited, answer_question
from app.utils.errors import ApiError

queries_bp = Blueprint("queries", __name__, url_prefix="/api/v1")

RATINGS = ("up", "down")


def _log_query(user_id, session_id, document_id, question, result=None, error_code=None):
    """Persist one /ask exchange as a QueryLog row and return its id.

    Called on every path out of /ask: with `result` when the pipeline returned (status
    answered/unanswered from the result), or with `error_code` when it raised (status
    error). Logging failures too is what lets the pilot count rate-limit hits, which on a
    free tier are the main thing to watch (implementation-plan.md task 3.4)."""
    if result is not None:
        log = QueryLog(
            status="answered" if result["answered"] else "unanswered",
            answer_text=result["answer_md"],
            confidence=result["confidence"],
            response_ms=result["response_ms"],
            model=result["model"],
            input_tokens=result.get("input_tokens"),
            output_tokens=result.get("output_tokens"),
        )
    else:
        log = QueryLog(status="error", error_code=error_code)

    log.user_id = user_id
    log.session_id = session_id
    log.document_id = document_id
    log.query_text = question
    db.session.add(log)
    db.session.commit()
    return log.id


def _log_retrievals(log_id, hits, citations):
    """Persist every chunk retrieve() offered the model for one exchange as
    query_retrievals rows, marking which ones made it into the final citations.

    This has to come from `hits` (every retrieved chunk), not `citations` (only the
    cited subset) — the analytics ambiguity metric is precisely the gap between the two,
    so logging only the cited half would erase the signal it reads. A no-op when there's
    nothing to log: the empty-question and nothing-indexed paths through
    answer_question() never retrieved anything, and an error path never got this far."""
    if not hits:
        return
    cited_ranks = {c["n"] for c in citations}
    for hit in hits:
        db.session.add(
            QueryRetrieval(
                query_log_id=log_id,
                document_id=hit["document_id"],
                document_version_id=hit["version_id"],
                chunk_id=hit["chunk_id"],
                page=hit["page"],
                rank=hit["rank"],
                similarity=hit["similarity"],
                cited=hit["rank"] in cited_ranks,
            )
        )
    db.session.commit()


@queries_bp.post("/ask")
@jwt_required()
def ask():
    """Answer a natural-language policy question via the RAG pipeline (objective 2).

    Body: {question, document_id?, session_id?}. document_id scopes retrieval to one
    policy, which is what the reader page's panel sends; omitted, it searches the whole
    corpus. session_id is a client-generated id per chat panel, stored for analytics.
    Delegates everything past validation to answer_question(), which retrieves, calls the
    LLM, and returns (AnswerResult, hits) — the client gets AnswerResult (answer_md,
    citations, confidence, answered); `hits`, every chunk retrieved regardless of
    citation, is logged to query_retrievals but never sent over the wire. Every exchange
    is written to query_logs and its id returned as `log_id`, which is what the client
    rates against (see submit_feedback)."""
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

    session_id = data.get("session_id")
    if session_id is not None:
        if not isinstance(session_id, str) or not (1 <= len(session_id) <= 36):
            raise ApiError("validation_error", "session_id must be a string of at most 36 characters", 400)

    user_id = int(get_jwt_identity())

    try:
        result, hits = answer_question(question, document_id=document_id)
    except AnswerRateLimited:
        _log_query(user_id, session_id, document_id, question, error_code="rate_limited")
        raise ApiError(
            "rate_limited",
            "the answering service is busy right now; try again in a moment",
            429,
        )
    except AnswerError:
        _log_query(user_id, session_id, document_id, question, error_code="upstream_error")
        raise ApiError("upstream_error", "the answering service could not be reached", 502)

    log_id = _log_query(user_id, session_id, document_id, question, result=result)
    _log_retrievals(log_id, hits, result["citations"])
    result["log_id"] = log_id
    return jsonify(result)


@queries_bp.get("/queries/mine")
@jwt_required()
def list_mine():
    """The requesting user's own chat history with the AI assistant, newest first —
    every question they've put to POST /ask, however it turned out (answered,
    unanswered, or a provider hiccup), so they can find something they asked before
    without needing to remember to bookmark it. `?page=`, `?per_page=` (default 20, max
    100). Distinct from GET /escalations/mine: that's the subset handed off to an admin;
    this is everything, including exchanges the AI resolved on its own."""
    user_id = int(get_jwt_identity())
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

    # id as a tiebreaker: created_at has second resolution, and two questions asked
    # inside the same second would otherwise sort arbitrarily against each other.
    pagination = (
        QueryLog.query.filter_by(user_id=user_id)
        .order_by(QueryLog.created_at.desc(), QueryLog.id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify(
        {
            "items": [log.to_dict() for log in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
        }
    )


@queries_bp.post("/queries/<int:log_id>/feedback")
@jwt_required()
def submit_feedback(log_id):
    """Rate one logged answer: thumbs up or down, with an optional comment.

    Body: {rating: "up"|"down", comment?}. Only the person who asked can rate their own
    query (anyone else's log id 404s rather than 403s, so ids can't be probed). A query
    has at most one rating, and posting again replaces it: the client sends the rating
    the moment a thumb is clicked, then re-posts with the comment if the user adds one.
    `comment` is only touched when the key is present, so a re-rate without it keeps
    whatever comment was already saved."""
    user_id = int(get_jwt_identity())
    log = QueryLog.query.get(log_id)
    if not log or log.user_id != user_id:
        raise ApiError("not_found", f"query {log_id} does not exist", 404)

    data = request.get_json(silent=True) or {}

    rating = data.get("rating")
    if rating not in RATINGS:
        raise ApiError("validation_error", f"rating must be one of {RATINGS}", 400)

    comment_given = "comment" in data
    comment = data.get("comment")
    if comment_given and comment is not None:
        if not isinstance(comment, str):
            raise ApiError("validation_error", "comment must be a string", 400)
        comment = comment.strip() or None
        if comment and len(comment) > 1000:
            raise ApiError("validation_error", "comment must be at most 1000 characters", 400)

    feedback = log.feedback
    if feedback is None:
        feedback = Feedback(query_log_id=log.id, user_id=user_id)
        db.session.add(feedback)
    feedback.rating = rating
    if comment_given:
        feedback.comment = comment
    db.session.commit()

    return "", 204
