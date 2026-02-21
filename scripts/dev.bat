@echo off
setlocal

set ROOT=%~dp0..
set BACKEND=%ROOT%\backend
set FRONTEND=%ROOT%\frontend

if "%1"=="--no-mongo" goto skipmongo
start "mongo" cmd /c "cd /d %ROOT% && mongod --dbpath .mongo-data"

:skipmongo
start "backend" cmd /c "cd /d %BACKEND% && python -m uvicorn main:app --host 127.0.0.1 --port 8000"
start "frontend" cmd /c "cd /d %FRONTEND% && npm run dev -- --host 127.0.0.1 --port 5173"

echo Backend:  http://127.0.0.1:8000/docs
echo Frontend: http://127.0.0.1:5173
