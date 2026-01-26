# Repo Agent Guide (makeup-boot)
Small FastAPI + SQLModel app with MySQL backend and an APScheduler-driven task runner.

## Build / Lint / Test Commands

### Setup (local)
```bash
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

python -m pip install -r requirements.txt
```

### Run the server
```bash
# Default (reads APP_HOST/APP_PORT from .env via app/config.py)
python run_server.py

# Direct uvicorn (equivalent entrypoint)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8569
```

Config notes:
- Default env file is repo-root `.env`; override with `ENV_FILE=/path/to/.env.xxx`.
- See `env.example` for required env vars.

### One-off scripts
```bash
python get_port.py          # print configured port
python check_config.py      # validate Cloudflare R2 config/client init
python test_config.py       # debug .env loading (redacts secrets)
python reassign_tasks.py    # rebalance pending task schedules (writes to DB)
python migrate_task_type.py # alters MySQL enum type (use with care)
```

### SQL scripts
- Manual SQL helpers in repo root: `delete_unused_tables.sql`, `fix_table_types.sql`, `migrate_task_type_enum.sql`.
- No migration framework (no Alembic); treat these as ops/manual scripts.

### Lint / format / typecheck
- No dedicated tooling found (`pyproject.toml`/`ruff.toml`/`pytest.ini` absent).
- Lightweight sanity check (no extra deps):

```bash
python -m compileall app
```

### Tests
- No test suite present (no `tests/`; `test_config.py` is a script).
- If/when pytest is introduced, standard patterns (incl. single test):

```bash
pytest
pytest tests/test_something.py
pytest tests/test_something.py::test_happy_path
pytest -k happy_path
```

## Code Style Guidelines (match existing patterns)

### Python version / typing
- Code uses modern typing (e.g. `dict[int, ...]`), so assume Python 3.9+.
- Add type hints for public functions and non-trivial logic.
- Use `Optional[T]` for nullable values.

### Files and module layout
- App entrypoint: `app/main.py` (`create_app()` returns FastAPI instance).
- Web routes/templates: `app/web/routes.py`, templates in `app/web/templates/`.
- DB setup: `app/db.py` (engine + session helpers).
- Background execution: `app/services/scheduler.py` + `app/services/task_runner.py`.

### Imports
- Group imports: stdlib, third-party, then local `app.*`.
- Keep imports at module top unless avoiding circular imports.
- Avoid wildcard imports.

### Formatting
- 4-space indentation.
- Triple-quoted docstrings for modules and functions; first line is a short summary.
- No strict line-length enforced; keep lines readable.

### Naming
- `snake_case` for modules/functions/variables.
- `PascalCase` for classes; `UPPER_SNAKE_CASE` for constants.
- Enums use `class X(str, enum.Enum)` (see `app/models.py`).

### FastAPI patterns
- Use `HTTPException` for request-level failures.
- JSON endpoints return `JSONResponse` or plain dict; keep error payloads consistent.
- Router lives in `app/web/routes.py` and is included from `app/main.py`.

### Database (SQLModel / SQLAlchemy)
- Use `sqlmodel.Session` and `session.exec(select(...))`.
- On write errors: `session.rollback()` before returning/raising.
- `app/db.py` intentionally does NOT call `SQLModel.metadata.create_all()` (tables pre-exist).

### Error handling
- Avoid silent failures. If catching broad `Exception`, log enough context to debug.
- Prefer structured error returns (many handlers use `{"success": False, "error": ...}`).
- If you must ignore an error, add a short comment explaining why.

### Logging / debugging
- Uses `print()` with tags like `[Scheduler]`, `[TaskRunner]`, `[DEBUG]`.
- Do not log secrets; if printing tokens/keys, print only a short prefix.

### Time handling
- Store/query UTC (`datetime.utcnow()`); UI often displays Beijing time.
- Reuse helpers like `to_beijing_time()` in `app/web/routes.py` and `beijing_now()` in `app/models.py`.

### Config / secrets
- Env vars are documented in `env.example`.
- Never commit `.env` files (gitignored).
- If adding new settings: update `app/config.py` and `env.example` together.

## Runtime Notes / Gotchas

### Scheduler / task runner
- The scheduler is started from `app/services/scheduler.py` and runs every 20s.
- Task execution is primarily implemented in `app/services/task_runner.py`.
- `run_task()` uses a thread + 20s timeout; keep task handlers idempotent and defensive.
- Prefer logging with existing tags (`[Scheduler]`, `[TaskRunner]`) when adding debug output.

### Static assets / templates
- Templates are in `app/web/templates/`.
- Static files are served from `/static` (mounted in `app/main.py`).

### Database / schema management
- Tables are assumed to pre-exist in MySQL; do not add `create_all()` calls by default.
- For schema changes, prefer explicit SQL scripts (repo root) and document any operational steps.

### Safety
- Do not log secrets. Redact tokens/keys (prefix-only) and never print full `OPENAI_API_KEY`.
- Avoid destructive ops (dropping tables, mass deletes) unless the user explicitly requests it.

## Cursor / Copilot Rules
No Cursor rules found in `.cursor/rules/` or `.cursorrules`.
No Copilot instructions found in `.github/copilot-instructions.md`.
