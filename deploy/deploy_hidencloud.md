# Deploy AGENT007 on HidenCloud (Free)

## Step 1: Create a free server

1. Go to https://dash.hidencloud.com/store/view/349
2. Click **Build my free server**
3. Pick a location (try different ones if "Failed to generate" appears)
4. Wait for the server to be created (~30-60 seconds)

## Step 2: Upload AGENT007

1. Go to https://panel.hidencloud.com (login with same account)
2. Go to **Management** → **File Manager**
3. Delete any default files (if any)
4. Click **Upload** and select `AGENT007-deploy.zip`
5. Once uploaded, click the **...** next to the zip → **Decompress**
6. Refresh the page to see all files extracted

## Step 3: Set startup command

1. In the HidenCloud panel, go to **Startup** tab
2. Set startup command: `python run.py`
3. Make sure Python version is set to **3.11** or **3.12**

## Step 4: Start the server

1. Click **Start**
2. Wait 1-2 minutes for dependencies to install (first time)
3. Check the **Console** tab for logs
4. You should see: `AGENT007 starting...` and `Wallet connected: True`
5. Get your server URL from the panel — dashboard is at `http://your-server-url:5000`

## Step 5: Weekly renewal

Every 7 days:
1. Go to https://dash.hidencloud.com/dashboard
2. Filter by "suspended"
3. Click **Renew** → **Create Invoice** → **Pay** (€0, free)

## Dashboard

Once running, open `http://your-server-url:5000` to see:
- Wallet balance (USDC on Base)
- Tasks found and bids placed
- Earnings
- Agent decisions
- Live logs
