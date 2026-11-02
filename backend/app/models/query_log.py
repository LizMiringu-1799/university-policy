from datetime import datetime

from app.extensions import db


class QueryLog(db.Model):
    """One question put to the RAG pipeline and what came back.

    Written once per POST /ask, after the answer (or failure) is known, so a row is the
    complete record of that exchange rather than something opened first and finalized
    later. Its id is what the client rates against (Feedback) and what the analytics in
    objectives 4 and 5 will read.
    """

    __tablename__ = "query_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    # Client-generated, one per chat panel mount. Lets analytics group a user's
    # rephrasings of the same question; it can't be reconstructed after the fact, which
    # is why it ships with the table rather than waiting for the dashboard to need it.
    session_id = db.Column(db.String(36), nullable=True, index=True)
    # Set when the question was scoped to one policy (the reader page's panel).
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
    query_text = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum("answered", "unanswered", "error", name="query_log_status"), nullable=False, index=True
    )
    answer_text = db.Column(db.Text, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    response_ms = db.Column(db.Integer, nullable=True)
    model = db.Column(db.String(60), nullable=True)
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    # The ApiError code the client received when status is "error" (rate_limited,
    # upstream_error); NULL otherwise.
    error_code = db.Column(db.String(40), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = db.relationship("User")
    document = db.relationship("Document")
    feedback = db.relationship("Feedback", uselist=False, back_populates="query_log")

    def to_dict(self):
        """Public JSON shape for one logged exchange, for the asker's own chat history
        (GET /queries/mine). Per-citation page numbers aren't included — the answer's
        inline [n] markers still render, just without the clickable source links
        AiQueryPanel builds live (those come from `retrievals`, which carries chunk/page
        detail, not from this dict; see QueryRetrieval below)."""
        return {
            "id": self.id,
            "question": self.query_text,
            "status": self.status,
            "answer_md": self.answer_text,
            "confidence": self.confidence,
            "document": {"id": self.document.id, "title": self.document.title} if self.document else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "rating": self.feedback.to_dict() if self.feedback else None,
        }


class QueryRetrieval(db.Model):
    """One chunk offered to the LLM as context for one logged query — every retrieved
    chunk, not just the ones that ended up cited.

    Written by the /ask route right after the QueryLog row it belongs to (answer.py's
    retrieve() stays side-effect-free; it has no query_log_id to attach to until the
    whole exchange is logged — see queries.py's `_log_retrievals`). This supersedes the
    original plan of threading a `query_log_id` through `retrieve()` itself, which would
    need the QueryLog row to exist before retrieval runs; simpler to log the full
    retrieval picture once, after the fact, from the hit list `answer_question()` already
    computed.

    The gap between "retrieved often" (`times_retrieved`) and "cited rarely"
    (`times_cited`) is what the analytics dashboard's ambiguity metric reads
    (implementation-plan.md §4.4): a policy the retriever keeps surfacing and the model
    keeps finding unhelpful. Kept for every query regardless of outcome — an `unanswered`
    query cites nothing and so has no confidence signal, but it still retrieved
    *something*, which is exactly the queries this table makes visible.
    """

    __tablename__ = "query_retrievals"

    id = db.Column(db.Integer, primary_key=True)
    query_log_id = db.Column(db.Integer, db.ForeignKey("query_logs.id"), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True)
    document_version_id = db.Column(db.Integer, db.ForeignKey("document_versions.id"), nullable=False)
    chunk_id = db.Column(db.String(80), nullable=False)
    page = db.Column(db.Integer, nullable=True)
    # Position in that one retrieval call (1 = best match). `rank` is a reserved word in
    # MySQL 8; SQLAlchemy quotes it automatically in the generated SQL.
    rank = db.Column(db.Integer, nullable=False)
    similarity = db.Column(db.Float, nullable=False)
    cited = db.Column(db.Boolean, nullable=False, default=False)

    query_log = db.relationship("QueryLog", backref="retrievals")
    document = db.relationship("Document")


class Feedback(db.Model):
    """A thumbs up/down, with an optional comment, from the person who asked, on one
    logged answer. One row per query: rating again updates this row rather than
    recording a second opinion, so a mis-click or a comment added afterwards is a second
    POST to the same endpoint, not a second record."""

    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    query_log_id = db.Column(db.Integer, db.ForeignKey("query_logs.id"), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Enum("up", "down", name="feedback_rating"), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    query_log = db.relationship("QueryLog", back_populates="feedback")
    user = db.relationship("User")

    def to_dict(self):
        """Public JSON shape for one rating."""
        return {
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }
