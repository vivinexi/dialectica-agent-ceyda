#!/usr/bin/env python3
"""Dialectica provider command: prompt on stdin -> Groq gpt-oss-20b answer on stdout.

Reads the full Dialectica job prompt from stdin, sends it as one chat
completion to Groq's free tier (openai/gpt-oss-20b), and prints only the
answer text. The Groq API key comes from the GROQ_API_KEY environment
variable -- never put a key in this file.

Retries once on failure (the network path to api.groq.com stalls
intermittently). On a 429 rate-limit response it waits 65s before the
retry, because Groq's free-tier budget resets per minute -- an immediate
retry just earns another 429. Exits non-zero when no usable answer comes
back, so `trued serve` counts it as a provider failure instead of an
answer.

Stdlib only: no third-party packages needed.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

MODEL = "openai/gpt-oss-20b"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_TOKENS = 8192  # keeps a large-prompt call inside Groq's per-minute budget
TEMPERATURE = 0.1
# Groq rejects oversized payloads with HTTP 413. The Dialectica job body is
# CONDUCT + instructions + arena rules + earlier answers + output format;
# the bulk is the middle (earlier answers). Keep prompts under this size.
MAX_PROMPT_CHARS = 100_000
# Groq sits behind Cloudflare, which blocks urllib's default user agent
# with HTTP 403 (error code 1010). A python-requests user agent is accepted.
USER_AGENT = "python-requests/2.32.3"


def _trim_prompt(prompt):
    """Head + tail truncation for oversized prompts.

    The head holds the task definition (instructions, arena rules); the
    tail holds the output format and any server correction note. Only the
    middle -- earlier participants' answers -- is cut, with a marker saying
    so. Returns the prompt unchanged when it already fits.
    """
    if len(prompt) <= MAX_PROMPT_CHARS:
        return prompt
    head_len = 60_000
    marker = (
        "\n\n[... %d characters of earlier discussion trimmed to fit "
        "the provider's payload limit ...]\n\n"
        % (len(prompt) - MAX_PROMPT_CHARS)
    )
    tail_len = MAX_PROMPT_CHARS - head_len - len(marker)
    trimmed = prompt[:head_len] + marker + prompt[-tail_len:]
    print(
        "dialectica provider: prompt %d chars trimmed to %d chars"
        % (len(prompt), len(trimmed)),
        file=sys.stderr,
    )
    return trimmed


def _call(prompt, api_key):
    """One Groq chat call. Returns (content, error): exactly one is set."""
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        return None, "HTTP %d: %s" % (exc.code, detail)
    except Exception as exc:  # noqa: BLE001 - network errors are retryable
        return None, str(exc)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None, "unexpected response shape: %s" % json.dumps(data)[:500]
    if content and content.strip():
        return content, None
    finish = data["choices"][0].get("finish_reason")
    return None, "empty content (finish_reason=%s)" % finish


def main():
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("dialectica provider: GROQ_API_KEY is not set", file=sys.stderr)
        return 1
    prompt = _trim_prompt(sys.stdin.read())
    if not prompt.strip():
        print("dialectica provider: empty prompt on stdin", file=sys.stderr)
        return 1
    content, err = _call(prompt, api_key)
    if content is None:
        if "429" in str(err):
            time.sleep(65)  # Groq free-tier budget resets per minute
        content, err = _call(prompt, api_key)
    if content is not None:
        sys.stdout.write(content)
        return 0
    print("dialectica provider: groq failed: %s" % err, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
