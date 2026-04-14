# Dco Second Brain — Setup Guide

## Overview
- **Frontend**: Vercel (Next.js)
- **Backend**: Railway (FastAPI)
- **Database**: Supabase (PostgreSQL + pgvector)
- **Ingestion**: GitHub Actions (every 6 hours)

---

## Step 1 — Get API Keys

### Anthropic (Claude API)
1. Go to https://console.anthropic.com
2. Sign in or create an account
3. Click **API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-`)
5. Add a credit card (you'll be charged per use — expect ~$5/month for a small team)

### Voyage AI (already done)
Key: `pa-dkMHrVi0nl2du5W9yhoXNs3OC-To7R1uswAavbcDtWH`

---

## Step 2 — Create Supabase Database

1. Go to https://supabase.com → **New Project**
2. Name it `dco-second-brain`, set a strong password
3. Once created, go to **Settings** → **Database**
4. Copy the **Connection String (URI)** — looks like:
   `postgresql://postgres:[YOUR-PASSWORD]@db.xxx.supabase.co:5432/postgres`
5. pgvector is pre-enabled on Supabase — no extra setup needed

---

## Step 3 — Create Slack Bot

1. Go to https://api.slack.com/apps → **Create New App** → **From Scratch**
2. App name: `Dco Second Brain` — select your workspace
3. In the left sidebar, click **OAuth & Permissions**
4. Under **Bot Token Scopes**, add:
   - `channels:history`
   - `channels:read`
   - `chat:write`
   - `commands`
5. Click **Install to Workspace** → **Allow**
6. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
7. Go to **Basic Information** → copy **Signing Secret**
8. After deploying to Railway, come back here:
   - **Event Subscriptions** → turn on, set Request URL to: `https://YOUR-RAILWAY-URL/slack/events`
   - Subscribe to bot event: `message.channels`
   - **Slash Commands** → Create: `/wiki`, Request URL: `https://YOUR-RAILWAY-URL/slack/events`
9. Invite the bot to your #research channel: `/invite @Dco Second Brain`

---

## Step 4 — Deploy Backend to Railway

1. Go to https://railway.app → sign in with GitHub
2. **New Project** → **Deploy from GitHub repo** → select `dco-second-brain`
3. Set root directory to `backend`
4. Railway will auto-detect Python and use the Dockerfile
5. Go to **Variables** tab, add all keys from `.env.example`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   VOYAGE_API_KEY=pa-dkMHrVi0nl2du5W9yhoXNs3OC-To7R1uswAavbcDtWH
   DATABASE_URL=postgresql://...  (from Supabase)
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_SIGNING_SECRET=...
   FRONTEND_URL=https://your-app.vercel.app
   ```
6. Copy the Railway deployment URL (e.g. `https://dco-second-brain.up.railway.app`)

---

## Step 5 — Deploy Frontend to Vercel

1. Go to https://vercel.com → **New Project** → import `dco-second-brain`
2. Set **Root Directory** to `frontend`
3. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://YOUR-RAILWAY-URL
   ```
4. Deploy — you'll get a URL like `https://dco-second-brain.vercel.app`
5. Update `FRONTEND_URL` in Railway to this Vercel URL

---

## Step 6 — First Ingestion

Once deployed, trigger the first Substack sync:
```bash
curl -X POST https://YOUR-RAILWAY-URL/api/ingest/substack
```

Or click **Sync Substack** on the Wiki page. This will crawl all Dco and Token Dispatch articles and add them to the knowledge base (takes 10-15 min first time).

---

## Step 7 — GitHub Actions (auto-sync every 6 hours)

1. Push this repo to GitHub
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Add secret: `API_URL` = `https://YOUR-RAILWAY-URL`
4. Done — ingestion runs automatically every 6 hours

---

## Running Locally (for development)

```bash
# 1. Start database
docker-compose up db -d

# 2. Backend
cd backend
cp .env.example .env   # fill in your values
pip install -r requirements.txt
uvicorn app.main:app --reload

# 3. Frontend
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/chat` | POST | Streaming chat with knowledge base |
| `/api/search?q=...` | GET | Hybrid semantic + keyword search |
| `/api/items` | GET | List all items (filter by source, tag) |
| `/api/items/:id` | GET | Get full item content |
| `/api/tags` | GET | All tags with counts |
| `/api/stats` | GET | Item counts by source |
| `/api/ingest/url` | POST | Manually ingest a URL |
| `/api/ingest/substack` | POST | Trigger Substack sync |
| `/api/ingest/twitter` | POST | Trigger Twitter sync |
| `/api/article/analyze` | POST | Analyze draft article |
| `/api/article/upload` | POST | Upload file for analysis |
| `/slack/events` | POST | Slack Events API webhook |

---

## Hyperagent Integration (Phase 2)

Once you have Hyperagent access, use it to:
1. Set up a scheduled agent that finds new research articles on topics you define
2. POST them to `/api/ingest/url` automatically
3. Generate weekly content briefs by calling `/api/search` with your planned article topics

The API is designed to accept external webhooks — Hyperagent can call any endpoint above.
