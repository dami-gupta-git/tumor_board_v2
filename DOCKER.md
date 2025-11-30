# TumorBoard Docker Guide

Simple guide to running TumorBoard with Docker.

## Quick Start

```bash
# 1. Set your API key
echo "OPENAI_API_KEY=your-key-here" > .env

# 2. Build and start
docker compose up -d

# 3. Open in browser
open http://localhost
```

That's it! The application is now running.

## What Gets Started

- **Backend API**: http://localhost:5000
- **Frontend Web App**: http://localhost

The frontend automatically proxies API requests to the backend.

## Common Commands

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Rebuild after code changes
docker compose up -d --build

# View status
docker compose ps
```

## Environment Variables

Create a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=sk-...

# Optional
ANTHROPIC_API_KEY=sk-ant-...
```

## Troubleshooting

**Can't connect to Docker daemon?**
```bash
# Start Docker Desktop first
```

**Port already in use?**
```bash
# Change ports in docker-compose.yml:
# - "8080:80"   # Frontend on port 8080
# - "8000:5000" # Backend on port 8000
```

**Need to see what's happening?**
```bash
# Follow all logs in real-time
docker compose logs -f

# Just backend logs
docker compose logs -f backend

# Just frontend logs
docker compose logs -f frontend
```

**Containers won't start?**
```bash
# Check if .env file exists and has your API key
cat .env

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d
```

## Architecture

```
┌─────────────────────────────────────┐
│          Docker Network             │
│  ┌──────────┐    ┌──────────────┐  │
│  │ Frontend │───▶│   Backend    │  │
│  │ (nginx)  │    │   (Flask)    │  │
│  │  :80     │    │   :5000      │  │
│  └──────────┘    └──────────────┘  │
└─────────────────────────────────────┘
```

- **Frontend**: Nginx serving Angular app, proxies `/api/*` to backend
- **Backend**: Flask API with uvicorn workers for async support

## Files

- `docker-compose.yml` - Service definitions
- `backend/Dockerfile` - Backend image build
- `frontend/Dockerfile` - Frontend image build (multi-stage)

## Production Notes

For production deployment:
1. Use proper SSL certificates
2. Set up monitoring and logging
3. Use secrets management for API keys
4. Configure proper resource limits
5. Set up automated backups

This is a research tool, not for clinical use.
