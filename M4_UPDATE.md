# M4 Hybrid Stability — Update Instructions

This patch is meant to be extracted into an existing M3 project root.
It does not contain or overwrite your `.env`.

PowerShell:

```powershell
cd D:\Desktop\telegram_ai_secretary
Copy-Item .env .env.backup
Expand-Archive -Path D:\Desktop\telegram_ai_secretary_M4_hybrid_patch.zip -DestinationPath . -Force
python -m pip install -e ".[dev]"
python -m alembic upgrade head
pytest
python -m app.telegram.run
```

Expected tests: `33 passed`.

Important: migration `0002_stability` is safe for both an existing M3 database and a fresh M4 database. Do not delete the PostgreSQL volume.
