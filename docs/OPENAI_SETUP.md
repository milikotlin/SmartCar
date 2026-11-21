# OpenAI chat: configure it and test it for real (without exposing the key)

The chat works **without a key** (it answers from a deterministic model built from the same facts, and says so). With a key, `gpt-4o-mini` writes the answer using **only** the facts produced by the system. This guide takes about 10 minutes. The real call to OpenAI **could not be tested during development** (no key was available): the test below is what remains to be done, once, before the presentation.

## 1. Create the key (on the OpenAI website)

1. Go to `platform.openai.com` (a ChatGPT subscription does **not** pay for the API; it is a separate API account).
2. *Billing*: add a small prepaid credit (a few dollars are enough) and set a **monthly limit** and a usage alert. That is your spending ceiling, independent of the code.
3. *API keys* → *Create new secret key* (preferably inside a project used only for this work). **Copy the key immediately**: it is not shown again.

## 2. Put the key in `.env` (and only there)

1. Open the `.env` file in the project folder with a text editor and fill in the line (no quotes, no spaces):
   `OPENAI_API_KEY=paste_the_key_here`
2. **Never** paste the key into a chat with Claude, into git, e-mail, slides or screenshots. `.env` is not committed (check: `git check-ignore -v .env` must point to `.gitignore`), and the frontend container does **not** receive this file.
3. Recreate the backend so that it reads the file again (a plain `restart` does not re-read `.env`):

```bash
docker compose up -d --force-recreate backend
```

## 3. Test

```bash
python scripts/check_openai.py --direct
```

* The script calls your own `POST /api/v1/chat` and prints where the answer came from (`source`), the model and the start of the text; with `--direct` it also asks OpenAI itself whether the key is accepted for the model. **It never prints the key**: it reads it from your `.env` and sends it only to `api.openai.com`.
* Expected result: `source: openai | model: gpt-4o-mini` and `OpenAI answered HTTP 200: key accepted`.
* Then, in the dashboard, open the chat and ask a question: the answer should say that it came from the language model (and not "rule-based").

| What you see | Meaning | What to do |
|---|---|---|
| `source: deterministic_fallback`, note `no OPENAI_API_KEY configured` | The backend does not see the key | Empty key in `.env`, or the backend was not recreated (step 2.3) |
| `--direct`: HTTP 401 | Key rejected (wrong, revoked, or copied with an extra character) | Create another and paste it without spaces |
| `--direct`: HTTP 429 | No credit, or the usage limit was reached | Check *Billing* and *Usage limits* |
| `--direct`: HTTP 404 | Model not available to the key | Change `OPENAI_MODEL` in `.env` (default `gpt-4o-mini`) |
| `--direct` 200 but the note says `language model call failed (...)` | Network, timeout (25 s) or an invalid response | Try again; the chat never breaks: it falls back to the deterministic model |

## 4. What is sent to OpenAI and what protects your spending

* Only the **system's facts** (make, model, year, fuel type, ownership type, estimated or measured mileage, risk levels, maintenance rules, recalls) plus the user's question (up to 1,000 characters). **The plate is not sent** (test `test_the_plate_is_not_sent_to_the_language_model`), and neither is any owner data (the system has none). The user's text never enters the system prompt (instruction-injection test).
* The backend limits the chat to **15 questions per minute per address** and each answer has a bounded length; on top of that comes the monthly limit you set in step 1.
* If the call fails, the note shows only the **type** of the error, never headers or the key.

## 5. After the presentation

Revoke the key under *API keys* (or delete the line from `.env`) and recreate the backend. To share the project always use `python scripts/make_share_zip.py`: it includes only tracked files, so `.env` never goes in.
