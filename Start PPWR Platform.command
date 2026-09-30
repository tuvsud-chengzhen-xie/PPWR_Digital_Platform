#!/bin/zsh
# PPWR Digital Platform — double-click launcher.
# Starts the app and opens it in the default browser. Close this window (or Ctrl+C) to stop.

cd "$(dirname "$0")"

PORT=8130
URL="http://127.0.0.1:${PORT}"

# Pick the interpreter that has (or can get) the dependencies — a Homebrew python3
# may block pip (PEP 668); the macOS system python accepts --user installs.
PY="python3"
if /usr/bin/python3 -c "import uvicorn" 2>/dev/null; then
    PY="/usr/bin/python3"
fi

echo "PPWR Digital Platform — TD & DoC service (CPS CoE × HDL)"
echo "Working directory: $(pwd)"

if curl -s -o /dev/null --max-time 2 "$URL"; then
    echo "Already running — opening ${URL}"
    open "$URL"
    exit 0
fi

echo "Installing/checking dependencies (first run may take a minute)…"
"$PY" -m pip install -q --user -r requirements.txt

(
    for i in {1..30}; do
        sleep 1
        if curl -s -o /dev/null --max-time 1 "$URL"; then
            open "$URL"
            exit 0
        fi
    done
) &

echo "Starting server on ${URL} — keep this window open."
exec "$PY" -m uvicorn app.main:app --port "$PORT" --loop asyncio
