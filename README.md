# hackldn26

Seat availability system with:
- `backend/`: FastAPI service for live table state, serial ingestion, mock jitter, and analytics
- `frontend/`: React + Vite UI that consumes `GET /api/tables`

## Run locally

### Recommended (one command)
- PowerShell: `.\scripts\dev.ps1`
- CMD: `.\scripts\dev.bat`

If MongoDB is already running elsewhere:
- PowerShell: `.\scripts\dev.ps1 -NoMongo`
- CMD: `.\scripts\dev.bat --no-mongo`

### Manual
1. Start MongoDB (required by default startup policy).
2. Backend:
   - `cd backend`
   - `python -m uvicorn main:app --host 127.0.0.1 --port 8000`
3. Frontend:
   - `cd frontend`
   - `npm install`
   - `npm run dev -- --host 127.0.0.1 --port 5173`

URLs:
- Backend docs: `http://127.0.0.1:8000/docs`
- Frontend: `http://127.0.0.1:5173`

## Quality gates

### Backend
- `cd backend`
- `python -m pytest tests -q`

### Frontend
- `cd frontend`
- `npm run build`
- `npm run test`

## Notes
- `/api/tables` is the primary UI contract.
- Occupancy is binary (`0` or `1`) in live state and API transforms.
- Runtime artifacts are intentionally ignored via root `.gitignore`.
