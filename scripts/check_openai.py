"""Real test of the OpenAI integration without ever showing the key.

Usage:  python scripts/check_openai.py [--direct] [http://localhost:8000]

1. Calls the running API (`POST /api/v1/chat`) and prints where the answer came from: `openai` (the language model answered) or `deterministic_fallback`
   (with the reason: no key configured, or the call failed). Only the source, model, note and the start of the answer are printed.
2. With --direct it also asks OpenAI itself whether the key in OPENAI_API_KEY (environment or the git-ignored .env) is accepted for the configured model, and prints
   ONLY the HTTP status and what it means. The key is read from your own .env, sent only to api.openai.com, and never printed.
"""
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
API = args[0] if args else "http://localhost:8000"
DIRECT = "--direct" in sys.argv


def env_value(name: str) -> str:
    value = os.environ.get(name, "")
    env = ROOT / ".env"
    if not value and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                value = line.split("=", 1)[1].strip()
    return value


def main() -> int:
    code = 0
    r = httpx.post(f"{API}/api/v1/chat", json={"license_plate": "4908732", "message": "I hear a squeaking noise when I brake"}, timeout=60)
    if r.status_code != 200:
        print(f"API answered {r.status_code}: {r.text[:200]}")
        return 1
    b = r.json()
    print(f"source: {b['source']} | model: {b.get('model')} | note: {b.get('note')}")
    print(f"answer ({len(b['answer'])} characters): {b['answer'][:200].replace(chr(10), ' ')}...")
    print(f"facts sent to the language model: {len(b['context'])} lines (the only thing it sees about the vehicle)")
    if b["source"] == "openai":
        print("RESULT: the OpenAI model answered. Integration works.")
    else:
        print("RESULT: deterministic fallback. " + ("No key is configured in the backend (OPENAI_API_KEY empty, or the container was not recreated after editing .env)."
              if "no OPENAI_API_KEY" in (b.get("note") or "") else "A key is configured but the call failed: run with --direct to see why."))
        code = 2
    if DIRECT:
        key, model = env_value("OPENAI_API_KEY"), env_value("OPENAI_MODEL") or "gpt-4o-mini"
        if not key:
            print("--direct: OPENAI_API_KEY is empty in the environment and in .env.")
            return 1
        try:
            d = httpx.get(f"https://api.openai.com/v1/models/{model}", headers={"Authorization": f"Bearer {key}"}, timeout=30)
            meaning = {200: "key accepted and the model is available", 401: "key rejected (wrong, revoked or copied with extra characters)", 403: "key valid but without permission for this model/project",
                       404: "key accepted but this model name is not available to it", 429: "rate or quota problem (check billing and the usage limits)"}.get(d.status_code, "unexpected")
            print(f"--direct: OpenAI answered HTTP {d.status_code}: {meaning}.")
        except httpx.HTTPError as exc:
            print(f"--direct: could not reach OpenAI ({type(exc).__name__}).")
            return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
