// Launches the Flask dev server with the backend's venv interpreter.
//
// This exists because the venv layout is platform-dependent: POSIX puts the interpreter
// in venv/bin/python, Windows in venv/Scripts/python.exe. Hardcoding either one into the
// npm script silently breaks `npm run dev` on the other platform -- concurrently reports
// the backend as exited, the frontend comes up fine, and the browser just says
// "Failed to fetch" against a port nothing is listening on.

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const backendDir = path.join(__dirname, "..", "backend");
const candidates = [
  path.join(backendDir, "venv", "Scripts", "python.exe"),
  path.join(backendDir, "venv", "bin", "python"),
];

const python = candidates.find((candidate) => fs.existsSync(candidate));

if (!python) {
  console.error(
    "No venv interpreter found under backend/venv.\n" +
      "Create one first:\n" +
      "  python -m venv backend/venv\n" +
      "  backend/venv/Scripts/pip install -r backend/requirements.txt   (Windows)\n" +
      "  backend/venv/bin/pip install -r backend/requirements.txt       (macOS/Linux)"
  );
  process.exit(1);
}

const child = spawn(python, ["run.py"], { cwd: backendDir, stdio: "inherit" });
child.on("exit", (code, signal) => process.exit(signal ? 1 : code ?? 1));
