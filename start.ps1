# Start Backend
Write-Host "Starting Backend Services (PostgreSQL, Redis, API)..."
docker compose up -d
docker compose exec api alembic upgrade head

# Start Frontend
Write-Host "Starting Frontend (Vite)..."
cd frontend
npm install
npm run dev:local
