# Third-party inspiration / provenance

M4 remains the **Telegram AI Secretary** codebase. It was not replaced by another project. We reviewed public projects and adopted compatible design patterns into our own architecture.

## telegram-business-bridge

Repository: https://github.com/AndyShaman/telegram-business-bridge  
License: MIT

Patterns adopted/reimplemented in our code:
- connection recovery when `business_connection` was not observed;
- approval-first reply safety;
- superseded/stale draft handling;
- persistent conversation archive used as AI context;
- prompt-injection trust boundary;
- keeping the Telegram sender path separate from the AI/provider layer.

Our implementation uses PostgreSQL/SQLAlchemy and our existing Conversation/Approval models rather than its SQLite/MCP architecture.

## hermes-telegram-business

Repository: https://github.com/NousResearch/hermes-telegram-business  
License: MIT

Patterns adopted/reimplemented:
- owner-only approval controls;
- fail-closed check when Telegram does not grant reply permission;
- draft expiry;
- burst/debounce behavior;
- stale context protection before sending.

We keep aiogram, our own DeepSeek/Gemini provider split, and our database model rather than the Hermes plugin runtime.

## rag-telegram-bot

Repository: https://github.com/Erlaio/rag-telegram-bot  
License: MIT

Pattern adopted/reimplemented:
- retrieval-before-generation / grounded-answer architecture;
- provider-independent knowledge layer.

M4 intentionally does **not** import LangChain/FAISS yet. For a personal small KB we retrieve from PostgreSQL deterministically, with a clean interface that can later be replaced by embeddings/vector search.

## Licensing note

The M4 changes are our own implementation of these patterns. No third-party repository has been vendored into this project. If future work copies or vendors source code directly, its license and attribution must be preserved in the repository.
