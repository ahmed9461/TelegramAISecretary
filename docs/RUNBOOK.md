# Runbook — M4

## Requirements
- Python 3.12+
- Docker Desktop on Windows, or PostgreSQL 16/17
- Telegram bot with Secretary Mode enabled
- Owner Telegram numeric ID
- DeepSeek API key for text/replies
- Gemini API key for image understanding

## Windows setup

```powershell
cd D:\Desktop\telegram_ai_secretary
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env`. Never paste API keys into Git.

## PostgreSQL

The default host port is `5433` and the container is bound only to `127.0.0.1`.

```powershell
docker compose up -d postgres
docker compose ps
```

Expected port:

```text
127.0.0.1:5433->5432/tcp
```

Run migrations:

```powershell
python -m alembic upgrade head
```

Existing M3 databases will apply `0002_stability`; do not delete the volume.

## Test

```powershell
pytest
```

Expected M4 result:

```text
33 passed
```

## Run polling bot

```powershell
python -m app.telegram.run
```

Open the bot from the owner account and send `/start` once so the bot can send approval cards to the owner.

## Telegram configuration
1. BotFather -> enable Secretary Mode.
2. Telegram -> Settings -> Business -> Chatbots -> connect the bot.
3. Grant read/manage-message access required by the use case.
4. Grant `Reply to messages` if you want approved drafts to be sent from your account.
5. Keep approval-first mode during live testing.

## Live verification sequence
1. Send `مرحبا` to the owner's personal account from a second Telegram account.
2. Wait for a draft card in the bot owner's DM.
3. Press Reject and confirm the contact receives nothing.
4. Send a second text, press Send, and confirm it arrives from the owner's personal account.
5. Send two messages quickly and confirm only the latest coherent context creates a useful draft.
6. Create a draft, then manually reply from the owner's account; the old draft must no longer send.
7. Edit a customer message before approving; the old draft must become invalid.
8. Send an image; Gemini should analyze it and DeepSeek should draft the reply.

## Knowledge commands

```text
/learn عام | اسم الخدمة | الاشتراك الشهري 10 دولارات
/learn داخلي | سياسة الخصم | لا تعط خصمًا تلقائيًا
/knowledge
/forgetknowledge 12
```

PRIVATE knowledge is not currently addable through the simple `/learn` command by design; sensitive data should not enter the LLM retrieval path.

Search archived messages:

```text
/search تجديد الاشتراك
```

## Failure behavior
- Gemini/DeepSeek 429/5xx: retry with exponential backoff; Gemini may try configured fallback models.
- Telegram `can_reply=false`: fail closed; no send attempt.
- Stale/expired/superseded approval: fail closed.
- Uncertain Telegram send exception: status becomes `UNCERTAIN`; no blind automatic retry.
- Missing `business_connection` update: first incoming message attempts `getBusinessConnection` recovery.
