import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    _db_user = os.environ.get("DB_USER", "root")
    _db_password = os.environ.get("DB_PASSWORD", "")
    _db_host = os.environ.get("DB_HOST", "localhost")
    _db_port = os.environ.get("DB_PORT", "3306")
    _db_name = os.environ.get("DB_NAME", "upman_db")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"mysql+pymysql://{_db_user}:{_db_password}@{_db_host}:{_db_port}/{_db_name}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # The ingestion worker holds a session across long embedding jobs, and MySQL drops
    # connections idle past wait_timeout. Without pre_ping it wakes up to a dead socket.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 3600}

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    PDF_STORAGE_DIR = os.environ.get("PDF_STORAGE_DIR", os.path.join(BASE_DIR, "data", "pdfs"))
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB upload cap, enforced on the stream

    # RAG. Chunk sizes are in characters and are deliberately sized to the embedding
    # model's 256-word-piece input window, not to the LLM context window: all-MiniLM-L6-v2
    # silently truncates past 256, so a larger chunk would be partly unretrievable.
    # See docs/design-rag.md §1.
    CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(BASE_DIR, "data", "chroma"))
    CHROMA_COLLECTION = os.environ.get("CHROMA_COLLECTION", "policies")
    RAG_CHUNK_CHARS = int(os.environ.get("RAG_CHUNK_CHARS", 850))
    RAG_CHUNK_MAX_CHARS = int(os.environ.get("RAG_CHUNK_MAX_CHARS", 1100))
    RAG_CHUNK_OVERLAP_CHARS = int(os.environ.get("RAG_CHUNK_OVERLAP_CHARS", 130))
    RAG_TOP_K = int(os.environ.get("RAG_TOP_K", 8))
    # Below this, a PDF is treated as scanned (no text layer) rather than silently indexed empty.
    RAG_MIN_CHARS_PER_PAGE = int(os.environ.get("RAG_MIN_CHARS_PER_PAGE", 100))

    # Answering LLM. Addressed through an OpenAI-compatible endpoint so the provider is a
    # base URL and a model string rather than a code dependency (docs/design-rag.md §9).
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    LLM_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", 1200))
    LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", 60))
    # Cited-chunk mean similarity below this marks a query unanswered even when the model
    # claims it answered. See docs/design-rag.md §9.
    RAG_CONFIDENCE_THRESHOLD = float(os.environ.get("RAG_CONFIDENCE_THRESHOLD", 0.35))
