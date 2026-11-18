#!/usr/bin/env bash
# Start the Dialectica Expert serve for agent Ceyda.
# Requires: the `trued` CLI (scripts/trued.py from the official Dialectica
# skill repo: https://github.com/dialectica-xyz/skills), a Dialectica agent
# token saved at ~/.dialectica/session (create one at
# https://dialectica.xyz/connect-agent), and GROQ_API_KEY in the environment.
# Put trued.py next to this script, or set TRUED_PY to its path.
# Run it detached (nohup/setsid) so it keeps serving; stop it by killing
# the `trued serve` process. Never start a second serve while one is alive
# (the serve.lock file guards this).
set -euo pipefail
cd "$(dirname "$0")"
: "${GROQ_API_KEY:?GROQ_API_KEY is not set}"
TRUED_PY="${TRUED_PY:-$(pwd)/trued.py}"
export DIALECTICA_PROVIDER_CMD="python3 $(pwd)/provider.py"
exec python3 "$TRUED_PY" serve --context-window 131072 --every 10m
