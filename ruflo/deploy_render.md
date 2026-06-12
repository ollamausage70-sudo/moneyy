# Deploy Ruflo MCP Server on Render

## Prerequisites
- AGENT007 repository pushed to GitHub
- Render account (free tier works)

## Step 1: Create a New Web Service

1. Go to https://dashboard.render.com
2. Click **New +** → **Web Service**
3. Connect your GitHub repo (same repo as AGENT007)
4. Fill in:

| Setting | Value |
|---------|-------|
| Name | `agent007-ruflo` |
| Region | Same as AGENT007 |
| Branch | `master` |
| Runtime | **Node** |
| Root Directory | `ruflo` |
| Build Command | `npm install` |
| Start Command | `npm start` |
| Plan | **Free** |

## Step 2: Environment Variables

| Key | Value |
|-----|-------|
| `PORT` | `4000` |
| `NODE_ENV` | `production` |

## Step 3: Deploy

Click **Deploy Web Service**. Wait 3-5 minutes.

Your Ruflo MCP URL will be: `https://agent007-ruflo.onrender.com`

## Step 4: Configure AGENT007 to Use Ruflo

Set this env var in AGENT007's Render dashboard:

| Key | Value |
|-----|-------|
| `RUFLO_MCP_URL` | `https://agent007-ruflo.onrender.com` |

## Step 5: Verify

```bash
curl https://agent007-ruflo.onrender.com/health
# => {"status":"alive","service":"ruflo-mcp"}
```

## Full Architecture

```
User → Render (AGENT007 Flask) ←→ Render (Ruflo MCP)
              │                          │
              ↓                          ↓
       Marketplaces                Swarm Agents
       (Yoyo, Dealwork,            (CEO, CFO, COO,
        OpenTask, uGig,             BizDev, Delivery,
        AgentHansa,                 QA, Learning,
        AnyTasks)                   Security, etc.)
              │
              ↓
         Base Network
         (USDC Wallet)
```
