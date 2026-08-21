# Progress

## 2026-08-21 — Milestone M0/M1 started

### Implemented
- Project package and Python configuration.
- FastAPI health/ready endpoints.
- SQLAlchemy data model for owners, Business Connections, contacts, conversations, messages, knowledge, menus, custom intents, flows, flow sessions, approvals and audits.
- Alembic baseline.
- Owner-only authorization primitive.
- Conversation state machine and effective-state resolver.
- Dynamic Menu/Button model with AI_ONLY/CUSTOM_MENU/HYBRID support.
- Generic Flow Engine with version-aware definition model.
- Core + Custom Intent primitives.
- Safe deterministic AI decision policy skeleton.
- Knowledge visibility primitive.
- Long-term memory safety primitive.
- Telegram MessagingAdapter contract.
- aiogram Business Connection / Business Message event bootstrap.
- aiogram outbound send using `business_connection_id`.
- Owner administration main keyboard.
- Unit/integration core test suite.

### Intentionally not enabled yet
- Autonomous AI replies.
- Live OpenAI provider.
- Persistence of Business events from aiogram handlers.
- Approval-send callback transaction.
- Rich Message renderer.
- Media download/transcription.

Reason: autonomous sending is blocked until persistence + idempotency + approval queue are wired end-to-end.

## 2026-08-21 — Persistence/approval safety gate

### Added
- Idempotent Business-message ingestion into Contact/Conversation/Message records.
- Business Connection upsert persistence.
- Conversation revision increments on new context.
- Approval candidates snapshot the conversation revision.
- Stale approvals are rejected after new incoming context.
- Approval claiming is one-shot (`PENDING -> SENDING`).
- Uncertain-send state is available; unsafe blind retries are avoided.
- aiogram handler now persists Business events but still does not autonomously reply.

## 2026-08-21 — Foundation verification

- Core tests: 18/18 passed locally.
- `compileall`: passed.
- Alembic `upgrade head`: passed against a fresh SQLite verification database.
- Schema verification: 15 tables including `alembic_version` created.
- GitHub Actions CI added for Python 3.12/3.13 with Ruff + compile + pytest.
- systemd service templates added for API and polling bot.

## 2026-08-21 — Milestone M2: Gemini Vision + DeepSeek reasoning

### Added
- `VisionProvider` abstraction.
- `GeminiVisionProvider` using Gemini structured image understanding.
- Default Gemini model configuration: `gemini-3.7-flash` (configurable).
- `DeepSeekAIProvider` using `/chat/completions`.
- Default DeepSeek model configuration: `deepseek-v4-flash` (configurable).
- DeepSeek classification output is filtered through the existing deterministic local safety policy.
- `MultimodalPipeline`: Gemini image evidence -> DeepSeek classification/reply.
- Image prompt-injection boundary: instructions visible inside an image are treated as untrusted content.
- Telegram photo download with configurable maximum size.
- End-to-end photo approval path for Telegram Business messages.
- Owner approval buttons: Send / Reject.
- One-shot approval sending and uncertain-send handling reused for image replies.
- Gemini/DeepSeek secrets and model settings added to `.env.example`.

### Safety status
- Image replies are **approval-only** in this milestone.
- Text autonomous AI replies remain disabled pending live Telegram verification.
- If Gemini or DeepSeek fails, no reply is sent to the contact; the owner is notified instead.

### Verification
- `compileall`: passed.
- Test suite: 22/22 passed.
- Provider tests use mocked HTTP transports; no real API keys are required for CI.
- Ruff CLI was not installed in the local execution environment, so local Ruff execution could not be repeated here; CI configuration still includes Ruff installation/checking.

## 2026-08-21 — Milestone M4: hybrid stability pass

### Open-source-informed stability improvements
- Reviewed `telegram-business-bridge`, `hermes-telegram-business`, and `rag-telegram-bot` (MIT projects) and reimplemented selected patterns in our architecture.
- Recover missing Telegram Business connection state through `getBusinessConnection` on first incoming message.
- Verify the live Telegram connection and `can_reply` right immediately before approved sends.
- Reject connections belonging to a Telegram user other than the configured owner.
- Per-chat debounce for burst messages; newer work cancels older pending AI work.
- Conversation-revision validation before a generated AI result can become an approval draft.
- New approvals supersede older pending approvals in the same conversation.
- Approval TTL defaults to 24 hours and expired drafts fail closed.
- Owner approval cards are updated to Sent / Rejected / Stale / Uncertain states.
- Approved outgoing replies are persisted to history for future context.
- Manual owner replies are stored as owner context and invalidate stale AI drafts rather than causing an AI feedback loop.
- Edited/deleted Business messages update archive metadata and invalidate pending drafts.
- Recent message history is fed to the AI with untrusted-content boundaries.
- DeepSeek transient failures now retry with exponential backoff.
- PostgreSQL knowledge retrieval feeds PUBLIC/INTERNAL knowledge into the model while excluding PRIVATE knowledge.
- Owner can add/list/delete knowledge from Telegram commands.
- Owner can search archived messages with `/search`.
- PostgreSQL Docker binding moved to localhost port 5433 by default to reduce local conflicts.
- Windows installs `psycopg-binary` automatically; base dependency remains portable `psycopg` for Termux/Linux.

### Database
- Added Alembic migration `0002_stability`.
- Approval rows now store owner approval-card IDs, send message ID, expiry timestamp.
- Message rows now store edit/delete timestamps.

### Verification
- `python -m compileall app`: passed.
- Test suite: **33/33 passed**.
- Tests now cover draft supersession, expiry, outgoing-history persistence, PRIVATE knowledge exclusion, prompt-injection marker integrity, transient DeepSeek retry, archive search, and debounce cancellation.
