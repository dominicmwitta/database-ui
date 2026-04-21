@echo off
cd /d %~dp0
start "API Server" cmd /k "python -m uvicorn macro_database.api:app --host 0.0.0.0 --port 8000 --reload"
start "Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"
