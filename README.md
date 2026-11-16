# daily agent

reads my calendar, obsidian tasks and school email, then tells me what to do first today. nearest deadline wins.

## status

built and tested: skeleton, write protection, data model, priority engine, /today endpoint.
next: google calendar.

## run it

    uv sync
    uv run pytest
    uv run uvicorn app.main:create_app --factory --reload

needs `API_TOKEN` and `DATABASE_URL` in a `.env` file. see `.env.example`.

## read these

1. `specs/00_principles.md` and `specs/01_overview.md` first
2. `docs/SETUP_CHECKLIST.md` for one time setup
3. `docs/CHECKIN_LOG.md` for progress
