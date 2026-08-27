import logging

from flask import Flask
from flask_cors import CORS

from app.config import Config
from app.extensions import db, migrate, jwt, bcrypt
from app.utils.errors import register_error_handlers, error_response


def _configure_logging():
    """Surface the app's own INFO logs.

    Ingestion runs on a background thread, so without this its progress and failures go
    nowhere: nothing in the console explains why a document is still 'pending'. Scoped to
    the `app` logger so third-party INFO chatter stays out.
    """
    logger = logging.getLogger("app")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def create_app(config_class=Config):
    """Application factory: builds and fully wires one Flask app instance.

    Initializes the extensions (db, migrate, jwt, bcrypt, CORS), registers every route
    blueprint and the CLI commands, and starts the background ingestion worker. Called
    once per process by run.py, and once per test by the test suite with a different
    config_class, which is the reason this is a factory rather than a module-level app.
    """
    _configure_logging()

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    register_error_handlers(app)

    from app.routes.auth import auth_bp
    from app.routes.documents import documents_bp
    from app.routes.admin_documents import admin_documents_bp
    from app.routes.queries import queries_bp
    from app.routes.escalations import escalations_bp
    from app.routes.admin_escalations import admin_escalations_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(admin_documents_bp)
    app.register_blueprint(queries_bp)
    app.register_blueprint(escalations_bp)
    app.register_blueprint(admin_escalations_bp)

    from app.cli import register_cli
    from app.rag import ingest

    register_cli(app)
    ingest.init_app(app)

    # flask-jwt-extended callbacks: without these it returns its own default JSON shape
    # on auth failure instead of the app's standard {error: {code, message}} envelope.
    @jwt.unauthorized_loader
    def handle_missing_token(reason):
        """No Authorization header/token was presented at all."""
        return error_response("unauthorized", "authentication required", 401)

    @jwt.invalid_token_loader
    def handle_invalid_token(reason):
        """A token was presented but failed to decode/verify (bad signature, malformed)."""
        return error_response("unauthorized", "invalid or expired token", 401)

    @jwt.expired_token_loader
    def handle_expired_token(jwt_header, jwt_payload):
        """A token decoded fine but its exp claim has passed."""
        return error_response("unauthorized", "invalid or expired token", 401)

    return app
