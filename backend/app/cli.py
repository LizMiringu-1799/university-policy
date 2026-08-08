import sys

import click

from app.extensions import db, bcrypt
from app.models.document import Document, DocumentVersion
from app.models.user import User
from app.rag import ingest, store
from app.rag.retrieval import retrieve


def console_safe(text):
    """Policy PDFs are full of characters a Windows cp1252 console cannot encode.

    Without this, printing a retrieved chunk raises UnicodeEncodeError and the search
    command dies on the one document you wanted to look at.
    """
    encoding = sys.stdout.encoding or "utf-8"
    return str(text).encode(encoding, errors="replace").decode(encoding, errors="replace")


def register_cli(app):
    @app.cli.command("seed-admin")
    @click.option("--name", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def seed_admin(name, email, password):
        """Create an admin account (bypasses the student-only register endpoint)."""
        email = email.strip().lower()
        if User.query.filter_by(email=email).first():
            click.echo(f"A user with email {email} already exists.")
            return

        user = User(
            name=name.strip(),
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            role="admin",
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin account created: {email}")

    DEMO_PASSWORD = "Pass@123"
    DEMO_USERS = [
        {"name": "Demo Student", "email": "student@dkut.ac.ke", "role": "student"},
        {"name": "Demo Admin", "email": "admin@dkut.ac.ke", "role": "admin"},
        {"name": "Demo Staff", "email": "staff@dkut.ac.ke", "role": "staff"},
    ]

    @app.cli.command("seed-demo")
    def seed_demo():
        """Create the three demo accounts (student/admin/staff), all with password Pass@123. Idempotent."""
        created = []
        for demo in DEMO_USERS:
            if User.query.filter_by(email=demo["email"]).first():
                continue
            user = User(
                name=demo["name"],
                email=demo["email"],
                password_hash=bcrypt.generate_password_hash(DEMO_PASSWORD).decode("utf-8"),
                role=demo["role"],
            )
            db.session.add(user)
            created.append(demo["email"])
        db.session.commit()
        if created:
            click.echo(f"Created demo accounts: {', '.join(created)}")
        else:
            click.echo("Demo accounts already exist; nothing to do.")

    @app.cli.command("reindex")
    @click.option("--document-id", type=int, help="Reindex one document instead of all active ones.")
    def reindex(document_id):
        """Rebuild the Chroma index for one document or the whole active corpus.

        Runs the indexing here rather than handing it to the server's queue, so you see
        the result. Stop the Flask server first: Chroma's persistent client expects one
        process against its data directory, and two writers corrupt the index rather
        than erroring.
        """
        query = DocumentVersion.query.join(
            Document, Document.current_version_id == DocumentVersion.id
        ).filter(Document.status == "active")
        if document_id:
            query = query.filter(Document.id == document_id)

        versions = query.all()
        if not versions:
            click.echo("No active documents to index.")
            return

        for version in versions:
            title = console_safe(version.document.title)
            click.echo(f"Indexing {title} (document {version.document_id}, v{version.version_number})... ", nl=False)
            ingest.index_version(version.id)
            db.session.refresh(version)
            if version.index_status == "indexed":
                click.echo(f"{version.chunk_count} chunks")
            else:
                click.echo(f"{version.index_status}: {console_safe(version.index_error)}")

        click.echo(f"Collection now holds {store.count()} chunks.")

    @app.cli.command("search")
    @click.argument("question")
    @click.option("--k", type=int, default=None, help="How many chunks to retrieve.")
    def search(question, k):
        """Print the top-k chunks for a question. The eyeball check on retrieval quality."""
        hits = retrieve(question, k=k)
        if not hits:
            click.echo("No results. Is anything indexed? Try: flask reindex")
            return

        for hit in hits:
            click.echo(
                f"\n[{hit['rank']}] {hit['similarity']:.3f}  {console_safe(hit['title'])}, page {hit['page']}"
            )
            click.echo(f"    {console_safe(hit['text'][:300])}...")
