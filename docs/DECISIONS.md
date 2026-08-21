# Architecture Decisions

## ADR-001 — Telegram is an adapter
**Status:** Accepted

Core conversation, flow, knowledge, memory and decision logic must not import aiogram.
Only `app/telegram/*` may depend on Telegram-specific types.

## ADR-002 — No vertical lock-in
**Status:** Accepted

Project/service/subscription/support buttons are examples only. Menus, custom intents and flows are data-driven.

## ADR-003 — Approval first
**Status:** Accepted

The first live mode is APPROVAL. Autonomous sending is enabled only after persistence, idempotency, state locking and evals are active.

## ADR-004 — PostgreSQL production, SQLite developer fallback
**Status:** Accepted

Production configuration uses PostgreSQL. A zero-dependency SQLite URL remains available for local core tests and health checks.

## ADR-005 — No AI before safety path
**Status:** Accepted

The Telegram handler may ingest Business messages in Phase 1 but must not autonomously answer until persistence + approval queue are active.

## ADR-004 — Gemini for vision, DeepSeek for reasoning/reply
**Date:** 2026-08-21
**Status:** Accepted

### Decision
Use a provider split for image messages:

1. Telegram downloads the image temporarily into memory.
2. Gemini is the `VisionProvider` and returns structured, grounded visual evidence only.
3. Image text is treated as untrusted content; instructions inside the image do not become system instructions.
4. DeepSeek receives the user's text plus Gemini's structured observation and performs intent/risk analysis and reply drafting.
5. The deterministic local policy still owns the final `AUTO / APPROVAL / ESCALATE / SILENT` gate.
6. During the current milestone, **all image replies remain approval-only**, even if the local policy considers a case safe for auto reply.

### Why
- Keeps multimodal perception separate from conversational reasoning.
- DeepSeek does not need native image input for this workflow.
- Vision provider can be replaced later without changing conversation/decision core.
- Prevents visual prompt-injection text from being interpreted as trusted instructions.
- Allows model routing and cost optimization independently per modality.

## ADR-007 — Hybridize by patterns, not by replacing the core
**Date:** 2026-08-21  
**Status:** Accepted

### Decision
Keep our PostgreSQL + aiogram + dynamic menus/flows + Gemini/DeepSeek architecture, while reimplementing proven safety/stability patterns found in MIT-licensed Telegram Business assistants.

### Rationale
- Avoid a rewrite into SQLite/MCP or a Hermes-specific plugin runtime.
- Preserve the dynamic product design already specified for subscriptions, services, support, and personal use.
- Reuse mature ideas where they solve known production failure modes: lost connection updates, stale approvals, burst messages, prompt injection, permission loss, and conversation context.

## ADR-008 — Approval drafts are durable state with expiry and revision binding
**Date:** 2026-08-21  
**Status:** Accepted

Every draft binds to a conversation revision and expiration time. A newer message/edit/delete or manual owner reply invalidates/supersedes old drafts. Sending always re-checks Telegram reply permission before the state transitions to SENDING.

## ADR-009 — PostgreSQL-first knowledge retrieval before vector infrastructure
**Date:** 2026-08-21  
**Status:** Accepted

For the current personal-scale knowledge base, use deterministic retrieval over active PostgreSQL knowledge items. PRIVATE rows never enter LLM context. Keep the retrieval interface replaceable so embeddings/vector search can be added once scale/quality measurements justify it.
