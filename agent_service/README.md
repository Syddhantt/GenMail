# GenMail Agent Service

LLM-powered intelligence layer for the GenMail email client. A standalone FastAPI service that talks to the GenMail REST API and exposes `/ai/*` endpoints powered by Google Gemini (free tier).

## Quickstart

```bash
# 1. Install
cd genmail_starter/agent_service
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Edit .env and paste your Gemini key from https://aistudio.google.com/apikey

# 3. Make sure GenMail is running on :5000 in another terminal:
#    cd ../server && uv run python main.py

# 4. Run the agent service
uvicorn app:app --port 5001 --reload

# 5. Verify
curl http://localhost:5001/health
```

Expected health response:

```json
{
  "ok": true,
  "provider": "gemini",
  "model_flash": "gemini-2.5-flash",
  "model_pro": "gemini-2.5-pro",
  "genmail_reachable": true,
  "genmail_url": "http://localhost:5000"
}
```

## Endpoints

| Phase | Method | Path | Feature |
|-------|--------|------|---------|
| 0 | GET | `/health` | Service + GenMail reachability check |
| A | POST | `/ai/summarize/{thread_id}` | F1 Thread Summarizer *(coming)* |
| A | GET | `/ai/digest` | F2 Unread Digest *(coming)* |
| A | GET | `/ai/sender-topics` | F3 Sender Topic Analysis *(coming)* |
| A | GET | `/ai/stats` | F4 Inbox Intelligence Stats *(coming)* |
| A | GET | `/ai/commitments` | F5 Commitment Tracker *(coming)* |
| A | POST | `/ai/urgency/{email_id}` | F6 Urgency Classifier *(coming)* |
| A | POST | `/ai/thread-state/{thread_id}` | F7 Thread State Classifier *(coming)* |
| A | POST | `/ai/draft-reply/{email_id}` | F8 Smart Reply Drafter *(coming)* |
| A | GET | `/ai/proactive` | F9 Proactive Inbox Surface *(coming)* |
| A | POST | `/ai/synthesize` | F10 Cross-Thread Synthesizer *(coming)* |

## Architecture

```
React UI (:5173) ──► Agent Service (:5001) ──► GenMail API (:5000)
                            │
                            ▼
                     Google Gemini (free)
                     + logs.db (every prompt/response)
```

The agent service never touches GenMail's SQLite directly — all reads go through the REST API. All LLM calls go through one facade (`llm/__init__.py`) so swapping providers is a one-line config change.

## Switching LLM provider

Edit `.env`:

```
LLM_PROVIDER=gemini   # primary, free
LLM_PROVIDER=groq     # fast fallback if Gemini Pro hits 100/day limit
LLM_PROVIDER=ollama   # offline / local
```

Restart the service. No code changes needed.

## Testing

```bash
uv run pytest
uv run ruff check .
```
