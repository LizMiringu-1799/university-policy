import os
import socket
import subprocess
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# Before anything can import onnxruntime. Left unset, the embedding model sizes its
# thread pool to the core count and starves the web server it shares this process with.
os.environ.setdefault("OMP_NUM_THREADS", "1")


def _ensure_mysql_running():
    """Start Homebrew's MySQL if it's down, so `python run.py` works without a
    separate `brew services start mysql` step. No-op off macOS (e.g. XAMPP on
    Windows, where MySQL is started from the XAMPP control panel instead)."""
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", 3306))

    def reachable():
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            return False

    if reachable() or sys.platform != "darwin":
        return

    print("MySQL not reachable, starting it via `brew services start mysql`...")
    try:
        subprocess.run(["brew", "services", "start", "mysql"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"Could not start MySQL via Homebrew: {exc}")
        return

    for _ in range(20):
        if reachable():
            print("MySQL is up.")
            return
        time.sleep(0.5)
    print("MySQL still not reachable after starting the service; check `brew services list`.")


_ensure_mysql_running()

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
