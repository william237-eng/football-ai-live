Deployment checklist and quick start

Prerequisites
- Python 3.11+ (3.14 tested in dev venv)
- Git (optional)

Setup (local)

1) Create and activate a virtualenv

Windows (Powershell):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

2) Install dependencies

```powershell
pip install -r requirements.txt
```

3) Run smoke tests (registry structure + imports)

```powershell
python -m scripts.test_registries_smoke
```

4) Launch the Streamlit app (development)

```powershell
streamlit run app.py
```

Production notes
- Ensure the `database/` directory is writable by the process (used by registries and sqlite files).
- The UI components rely on persisted prediction registries in `database/*.json` and `database/victory_predictions.db`.
- Use a process manager (systemd / PM2 / Docker) to run `streamlit run app.py` behind a reverse proxy for production.

CI recommendations (GitHub Actions)
- Run `python -m scripts.test_registries_smoke` in CI
- Lint / static checks (flake8 / mypy) if desired
- Optionally run a containerized Streamlit smoke test

Files changed
- modules/shared/stats_ui.py — added tolerant key mapping for `selected`.
- modules/top_under25_live/under25_ui.py — migrated stats display to shared `render_stats_block`.
- scripts/test_registries_smoke.py — smoke test helper to validate registry outputs.

If you want, I can add a minimal GitHub Actions workflow and a Dockerfile to fully containerize the app.