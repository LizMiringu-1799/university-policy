from datetime import datetime

from app.extensions import db


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum("active", "archived", name="document_status"), nullable=False, default="active")
    current_version_id = db.Column(
        db.Integer, db.ForeignKey("document_versions.id", use_alter=True, name="fk_documents_current_version")
    )
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions = db.relationship(
        "DocumentVersion",
        foreign_keys="DocumentVersion.document_id",
        backref="document",
        order_by="DocumentVersion.version_number",
    )
    current_version = db.relationship("DocumentVersion", foreign_keys=[current_version_id], post_update=True)

    def to_summary_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "status": self.status,
            "current_version": self.current_version.version_number if self.current_version else None,
            "page_count": self.current_version.page_count if self.current_version else None,
            "index_status": self.current_version.index_status if self.current_version else None,
            "chunk_count": self.current_version.chunk_count if self.current_version else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }

    def to_detail_dict(self):
        data = self.to_summary_dict()
        data["versions"] = [v.to_dict() for v in self.versions]
        return data


class DocumentVersion(db.Model):
    __tablename__ = "document_versions"
    __table_args__ = (db.UniqueConstraint("document_id", "version_number", name="uq_doc_version"),)

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_sha256 = db.Column(db.String(64), nullable=False)
    page_count = db.Column(db.Integer)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    index_status = db.Column(
        db.Enum("pending", "indexing", "indexed", "failed", name="version_index_status"),
        nullable=False,
        default="pending",
        index=True,
    )
    chunk_count = db.Column(db.Integer)
    index_error = db.Column(db.String(500))

    uploader = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "version_number": self.version_number,
            "page_count": self.page_count,
            "uploaded_at": self.uploaded_at.isoformat() + "Z" if self.uploaded_at else None,
            "uploaded_by": self.uploader.name if self.uploader else None,
            "index_status": self.index_status,
            "chunk_count": self.chunk_count,
            "index_error": self.index_error,
        }
