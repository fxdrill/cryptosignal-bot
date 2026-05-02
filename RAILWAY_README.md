# 🚀 CryptoSignal Pro — Railway Deployment Guide
## Step by Step from Zero to Live in 10 Minutes

---

## WHAT YOU NEED BEFORE STARTING
- Your Telegram Bot Token (from @BotFather)
- Your Telegram Channel username (e.g. @mycryptosignals)
- Your Telegram User ID (from @userinfobot)
- A GitHub account (free)
- A Railway account (free) — railway.app

---

## STEP 1 — PREPARE YOUR FILES

Your bot folder should contain exactly these files:
```
ExchangeBot/
├── bot.py
├── config.py
├── database.py
├── engine.py
├── formatter.py
├── requirements.txt
├── Procfile
├── runtime.txt
└── .gitignore
```

Make sure you have the latest versions of ALL these files
(the ones provided with this README).

---

## STEP 2 — CREATE GITHUB REPOSITORY

1. Go to **github.com** and sign in
2. Click the **"+"** button top right → **"New repository"**
3. Name it: `cryptosignal-bot`
4. Set to **Private** (important — keeps your code safe)
5. Click **"Create repository"**

---

## STEP 3 — PUSH YOUR FILES TO GITHUB

Open **Command Prompt** in your bot folder:

```
cd E:\My Bot Work\ExchangeBot
```

Run these commands one by one:

```bash
git init
git add .
git commit -m "Initial bot deploy"
git branch -M main
git remote add origin https://github.com/YOURUSERNAME/cryptosignal-bot.git
git push -u origin main
```

Replace `YOURUSERNAME` with your actual GitHub username.

> If git asks for login, use your GitHub username and a
> Personal Access Token (not your password).
> Get token at: github.com → Settings → Developer Settings
> → Personal Access Tokens → Tokens (classic) → Generate new

---

## STEP 4 — CREATE RAILWAY ACCOUNT

1. Go to **railway.app**
2. Click **"Start a New Project"**
3. Sign up with your **GitHub account** (easiest option)
4. Verify your account if asked

---

## STEP 5 — CREATE NEW PROJECT ON RAILWAY

1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Find and select your `cryptosignal-bot` repository
4. Click **"Deploy Now"**

Railway will start trying to deploy — it will fail at first
because we haven't added the environment variables yet.
That's fine, keep going.

---

## STEP 6 — ADD ENVIRONMENT VARIABLES (THE IMPORTANT STEP)

This is where you add your secret settings safely.

1. In Railway, click your project
2. Click the **"Variables"** tab
3. Add each variable below by clicking **"New Variable"**:

### REQUIRED Variables (must add these):

| Variable Name | Your Value | Example |
|--------------|-----------|---------|
| `TELEGRAM_TOKEN` | Your bot token from @BotFather | `7837513210:AAHle...` |
| `CHANNEL_ID` | Your channel username | `@mycryptosignals` |
| `ADMIN_IDS` | Your Telegram user ID | `404393380` |

### OPTIONAL Variables (Railway needs these to work properly):

| Variable Name | Value |
|--------------|-------|
| `PYTHONIOENCODING` | `utf-8` |

### HOW TO GET EACH VALUE:

**TELEGRAM_TOKEN:**
- Open Telegram → search @BotFather
- Send `/mybots` → select your bot → API Token
- Copy the full token

**CHANNEL_ID:**
- Use your channel username with @ symbol
- Example: `@mycryptosignals`
- If private channel: use the number ID like `-1001234567890`

**ADMIN_IDS:**
- Open Telegram → search @userinfobot
- Send `/start`
- Copy the "Id:" number shown
- If multiple admins: `404393380,987654321`

---

## STEP 7 — SET SERVICE TYPE TO WORKER

Railway by default tries to run a web server.
Your bot is a background worker — you need to tell Railway this.

1. Click your service in Railway
2. Click **"Settings"** tab
3. Scroll to **"Deploy"** section
4. Find **"Start Command"** and set it to:
```
python bot.py
```

Or Railway will automatically read your `Procfile` which says:
```
worker: python bot.py
```

---

## STEP 8 — REDEPLOY

1. Click the **"Deployments"** tab
2. Click **"Deploy"** or wait for auto-deploy
3. Click on the deployment to see live logs

You should see in the logs:
```
Connected: BYBIT
Connected: BINANCE
Connected: MEXC
Database initialized
Bot starting...
Background scanner started
Watchlist scanner started
```

If you see those — YOUR BOT IS LIVE! 🎉

---

## STEP 9 — TEST YOUR BOT

1. Open Telegram
2. Search for your bot by username
3. Send `/start`
4. You should see the welcome message with menu buttons
5. Tap **Trending Tokens** to test
6. Check your channel — signals will appear automatically

---

## TROUBLESHOOTING

### Bot not responding?
- Check Variables tab — make sure TELEGRAM_TOKEN is correct
- Check Deployments tab → click deployment → read error logs

### "Unauthorized" error in logs?
- Your TELEGRAM_TOKEN is wrong
- Copy it again from @BotFather carefully

### Channel not receiving signals?
- Make sure your bot is **Admin** of the channel
- In Telegram: Channel Settings → Administrators → Add Admin → search your bot
- Give it "Post Messages" permission

### Deployment fails with "ModuleNotFoundError"?
- Make sure requirements.txt is in your repo
- Check it has all the library names spelled correctly

### "Database" errors?
- This is normal on first run — bot creates the database automatically

---

## KEEPING THE BOT RUNNING 24/7

Railway's free tier gives you **$5 credit/month** which covers
a lightweight Python worker running 24/7.

To check usage:
- Railway dashboard → your project → **"Usage"** tab

If you run out of free credits:
- Add a payment method (very cheap, ~$1-3/month for a bot)
- Or upgrade to Hobby plan ($5/month flat)

---

## UPDATING YOUR BOT LATER

When you make changes to the code:

```bash
git add .
git commit -m "Update bot settings"
git push
```

Railway automatically detects the push and redeploys. 
Zero downtime — takes about 60 seconds.

---

## FILE STRUCTURE EXPLAINED

| File | Purpose | Push to GitHub? |
|------|---------|----------------|
| `bot.py` | Main bot logic | ✅ Yes |
| `config.py` | Settings (reads from env vars) | ✅ Yes (safe — no secrets) |
| `database.py` | User database logic | ✅ Yes |
| `engine.py` | Exchange + RSI engine | ✅ Yes |
| `formatter.py` | Message templates | ✅ Yes |
| `requirements.txt` | Python libraries list | ✅ Yes |
| `Procfile` | Tells Railway how to run | ✅ Yes |
| `runtime.txt` | Python version | ✅ Yes |
| `.gitignore` | Files to never push | ✅ Yes |
| `*.db` files | Database (auto-created) | ❌ Never |
| `*.log` files | Log files | ❌ Never |

---

## QUICK COMMAND REFERENCE

```bash
# First time setup
git init
git add .
git commit -m "Initial deploy"
git branch -M main
git remote add origin https://github.com/YOU/cryptosignal-bot.git
git push -u origin main

# Every update after that
git add .
git commit -m "what you changed"
git push
```

---

## YOUR BOT IS NOW:
- ✅ Running 24/7 on Railway servers
- ✅ Scanning Bybit, Binance, MEXC every 5 minutes
- ✅ Posting signals to your channel automatically
- ✅ Alerting users on their personal preferences
- ✅ Tracking watchlist tokens every 10 minutes
- ✅ Zero maintenance needed
