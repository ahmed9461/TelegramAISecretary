# Telegram AI Secretary — M4 Hybrid Stability

A configurable personal AI secretary for Telegram Secretary/Business connections.

M4 keeps our own architecture (PostgreSQL, dynamic menus/flows, Gemini vision + DeepSeek reasoning) and adopts proven design patterns from open-source Telegram Business assistants: connection recovery, approval-first drafts, draft expiry/supersession, message-history context, prompt-injection boundaries, edit/delete invalidation, and burst debouncing.

## What works in M4

- Official Telegram Secretary/Business connection through Bot API + aiogram 3.
- Recovery with `getBusinessConnection` when the original connection event was missed.
- Owner-only control and approval cards.
- Text: DeepSeek classification/reasoning -> owner approval -> send as your account.
- Image: Gemini vision -> DeepSeek reasoning -> owner approval -> send as your account.
- Retries for transient Gemini and DeepSeek `429/5xx` failures.
- Per-chat debounce: bursts are coalesced and older AI work is cancelled.
- Conversation revision guard: stale AI results cannot become valid drafts.
- Draft lifecycle: PENDING / SUPERSEDED / STALE / EXPIRED / SENDING / SENT / REJECTED / UNCERTAIN.
- Live Telegram permission check immediately before an approved send.
- Approved outgoing replies are saved into the conversation history.
- Manual owner replies are saved as context and invalidate pending drafts instead of triggering AI.
- Edited/deleted Business messages invalidate stale drafts.
- Recent-message context (default 12 messages).
- Small knowledge-base retrieval from PostgreSQL; PRIVATE knowledge never reaches the model.
- Prompt-injection trust boundary around contact-provided text.
- Owner knowledge commands:
  - `/learn عام | العنوان | المعلومة`
  - `/learn داخلي | العنوان | المعلومة`
  - `/knowledge`
  - `/forgetknowledge ID`
- Local archive search: `/search كلمة أو جملة`.
- Dynamic menu/flow/custom-intent core from earlier milestones remains intact.

## Safe default

M4 is still **approval-first**. AI can draft, but nothing is sent to the contact until the owner presses **✅ إرسال الرد**. This is intentional while live behavior is being validated.

## Windows quick start

```powershell
cd D:\Desktop\telegram_ai_secretary
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Fill `.env` with your Telegram, DeepSeek, and Gemini keys. PostgreSQL defaults to host port **5433** to avoid conflicts with a local PostgreSQL installation.

```powershell
docker compose up -d postgres
docker compose ps
python -m alembic upgrade head
pytest
python -m app.telegram.run
```

Expected test result for M4: **33 passed**.

## Updating an existing M3 database

Do **not** delete your Docker volume. Just apply the new migration:

```powershell
python -m alembic upgrade head
```

Migration `0002` adds approval lifecycle metadata and edited/deleted-message timestamps.

## AI routing

```text
Text:
Telegram -> context + knowledge -> DeepSeek -> local safety policy -> owner approval -> reply

Image:
Telegram image -> Gemini vision -> DeepSeek -> local safety policy -> owner approval -> reply
```

## Knowledge model

M4 deliberately keeps PostgreSQL as the source of truth. For a small personal knowledge base, deterministic local retrieval is simpler and more stable than running a second vector database. The retrieval interface is isolated so embeddings/vector search can be plugged in later without changing the Telegram or AI layers.

`PUBLIC` knowledge may be stated to contacts. `INTERNAL` knowledge may guide behavior but is labeled as internal and must not be disclosed. `PRIVATE` knowledge is excluded from retrieval sent to the LLM.

## Open-source design inspiration

See `docs/THIRD_PARTY_INSPIRATION.md`. M4 adapts architecture/safety patterns rather than replacing our project with another repository.

## Project docs

- `docs/MASTER_SPEC.md`
- `docs/DECISIONS.md`
- `docs/PROGRESS.md`
- `docs/RUNBOOK.md`
- `docs/THIRD_PARTY_INSPIRATION.md`
