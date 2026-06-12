# Deploy AGENT007 + Ruflo on Render

## Architecture

```
GitHub Repo
├── AGENT007/       → Render Web Service (Python/Flask)
└── ruflo/           → Render Web Service (Node.js/Ruflo MCP)
```

## Step 1: Deploy AGENT007 (Flask App)

1. Go to https://dashboard.render.com
2. **New +** → **Web Service**
3. Connect your GitHub repo
4. Fill in:

| Setting | Value |
|---------|-------|
| Name | `agent007` |
| Runtime | **Python 3** |
| Root Directory | `AGENT007` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn run:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120` |
| Plan | **Free** |

5. Add environment variables (all of them from `.env`):
   - `GEMINI_API_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN`
   - `WALLET_ADDRESS`, `WALLET_NETWORK`
   - `YOYO_API_KEY`, `DEALWORK_API_KEY`, `DEALWORK_AGENT_ID`
   - `OPENTASK_API_KEY`, `UGIG_API_KEY`, `AGENTHANSA_API_KEY`, `ANYTASKS_API_KEY`
   - `AGENT007_DATA_DIR=/tmp/agent007_data`

6. Click **Deploy Web Service**

## Step 2: Deploy Ruflo MCP Server

1. **New +** → **Web Service** (same repo)
2. Fill in:

| Setting | Value |
|---------|-------|
| Name | `agent007-ruflo` |
| Runtime | **Node** |
| Root Directory | `ruflo` |
| Build Command | `npm install` |
| Start Command | `npm start` |
| Plan | **Free** |

3. Environment: `PORT=4000`
4. Click **Deploy Web Service**
5. Add `RUFLO_MCP_URL` env var to AGENT007's service

## Step 3: Set Up Cron Job (keeps agent alive)

Since Render free tier spins down after 15 min of inactivity:

1. Go to https://cron-job.org (free)
2. Create Cronjob:
   - URL: `https://agent007.onrender.com/health`
   - Interval: **Every 5 minutes**
   - Method: `GET`
3. Save

## Step 4: View Dashboard

| Endpoint | Description |
|----------|-------------|
| `/` | Full dashboard |
| `/health` | Health check |
| `/cycle` | Trigger one cycle |
| `/debug` | Check env vars |
| `/api/status` | Agent status JSON |
| `/api/diagnostics` | Marketplace diagnostics |
| `/api/database` | Database status |
| `/api/csuite/status` | C-Suite org chart |

## Business Model Tiers

| Tier | Name | When |
|------|------|------|
| 1 | Automated Freelancer | Default — single agent earning |
| 2 | Agent Fleet | After $50+ cumulative profit |
| 3 | Agent-as-a-Service | After $200+ cumulative profit |
| 4 | White-Label Platform | After $1000+ cumulative profit |

Tier upgrades are automatic based on CFO profitability reports.
