from datetime import datetime

from app.extensions import db


class Escalation(db.Model):
    """A question handed off to a human admin.

    Created two ways: automatically when the RAG pipeline can't answer (`reason`
    "unanswered"), or by the student choosing to follow up on an answer they got
    (`reason` "clarification"). Either way the admin sees the original question plus
    whatever the system already told the student, so they know where to pick it up from.
    """

    __tablename__ = "escalations"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
    reason = db.Column(db.Enum("unanswered", "clarification", name="escalation_reason"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    system_answer_md = db.Column(db.Text, nullable=True)
    system_confidence = db.Column(db.Float, nullable=True)
    status = db.Column(db.Enum("open", "resolved", name="escalation_status"), nullable=False, default="open", index=True)
    admin_response = db.Column(db.Text, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    student = db.relationship("User", foreign_keys=[student_id])
    resolver = db.relationship("User", foreign_keys=[resolved_by])
    document = db.relationship("Document")

    def to_dict(self):
        """Public JSON shape for one escalation, used by both the student and admin
        endpoints. Includes the system's own answer/confidence alongside the admin's
        reply so either side can see the full history of a question in one payload."""
        return {
            "id": self.id,
            "student": {"id": self.student.id, "name": self.student.name} if self.student else None,
            "document": {"id": self.document.id, "title": self.document.title} if self.document else None,
            "reason": self.reason,
            "question": self.question,
            "system_answer_md": self.system_answer_md,
            "system_confidence": self.system_confidence,
            "status": self.status,
            "admin_response": self.admin_response,
            "resolved_by": self.resolver.name if self.resolver else None,
            "resolved_at": self.resolved_at.isoformat() + "Z" if self.resolved_at else None,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }
