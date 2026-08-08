import os

from dotenv import load_dotenv

load_dotenv()

# Before anything can import onnxruntime. Left unset, the embedding model sizes its
# thread pool to the core count and starves the web server it shares this process with.
os.environ.setdefault("OMP_NUM_THREADS", "1")

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
