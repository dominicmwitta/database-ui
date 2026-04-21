@echo off
cd /d %~dp0
python -m uvicorn macro_database.api:app --host 0.0.0.0 --port 8000 --reload
