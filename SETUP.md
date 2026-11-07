# Setup guide (do these in order)

Everything in the code already runs without any keys. Each key you add turns on one more real feature.
Check your progress any time with:

```bash
cd backend && .venv/bin/python scripts/check_keys.py
```

| Step | Who | Time | Needed for |
|------|-----|------|-----------|
| 1. Team repo (GitHub Classroom) | Both | 5 min | Sharing code |
| 2. `.env` file | Sheetal | 2 min | All keys |
| 3. Gemini key | Sheetal | 3 min | AI decisions (fallback works without it) |
| 4. ElevenLabs key | Sakshi | 3 min | Voice alert |
| 5. Devpost project | Either | 5 min | Submission |
| 6. Run the backend locally | Sheetal | 2 min | Everything |
| 7. Tiger Data | Sheetal | 10 min | Event log (optional, cut first if late) |
| 8. Vultr server | Sheetal | 20 min | Public URL for the demo |
| 9. Domain (GoDaddy Registry) | Sakshi | 15 min | Nice URL (optional) |

---

## 1. Team repo through GitHub Classroom

1. **One** of you opens **ubh.ac/github-classroom**, signs in to GitHub, accepts the assignment and **creates a team** (e.g. `lights-out-ai`).
2. The **other** person opens the same link and **joins that team** (don't create a second one).
3. Classroom makes a repo for you. Open it and copy its URL (green **Code** button → HTTPS).
4. Push this project to it (run in the `LightsOutAI` folder):
   ```bash
   git remote add origin <repo-url-from-step-3>
   git branch -M main
   git pull origin main --allow-unrelated-histories --no-edit   # only if the repo already has a README
   git add -A && git commit -m "Backend: API, detection, risk, Gemini decisions, deploy"
   git push -u origin main
   ```
5. Sakshi runs `git clone <repo-url>` and works inside `frontend/`.

> `.env` is git-ignored. Run `git status` before every commit and make sure `.env` is **not** listed.

## 2. Create the `.env` file

```bash
cp .env.example .env
```
Open `.env` (repo root, next to `.env.example`) and paste each key as you get it. No quotes, no spaces around `=`.
Send the finished file to Sakshi privately (Discord DM, not a public channel). Never paste keys into the repo.

## 3. Gemini API key (Google AI Studio)

1. Go to **https://aistudio.google.com/apikey** and sign in with a Google account.
2. Click **Create API key** (accept the terms; choose "Create in new project" if asked).
3. Copy the key (starts with `AIza…`) into `.env`:
   ```
   GEMINI_API_KEY=AIza...
   GEMINI_MODEL=gemini-3.8-flash
   ```
4. Check it: `cd backend && .venv/bin/python scripts/check_keys.py` → `PASS Gemini`.

If you hit a "quota" or "rate limit" error during the demo, nothing breaks: the backend falls back to the rule-based decision and the response shows `"source": "fallback"`.

## 4. ElevenLabs key (Sakshi's voice alert)

1. Sign up at **https://elevenlabs.io** (free tier is enough for a demo).
2. Click your profile (bottom-left) → **API Keys** → **Create API Key**. Give it "Text to Speech" and "Voices: read" access.
3. Pick a calm voice: **Voices** → open a voice → **⋯ → Copy voice ID**.
4. Add both to `.env`:
   ```
   ELEVENLABS_API_KEY=sk_...
   ELEVENLABS_VOICE_ID=...
   ```
5. `scripts/check_keys.py` → `PASS ElevenLabs`.

## 5. Devpost project

1. Open the hackathon's Devpost page → **Join hackathon**.
2. **Create project** → name it *Lights Out AI* → save a draft.
3. In the project, **Edit → Invite teammates** → add the other person's Devpost email or username. They accept from their email.
4. Leave it as a draft; the write-up is in [DEVPOST.md](DEVPOST.md) for Sunday.

## 6. Run the backend on your laptop

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Try every endpoint: **http://localhost:8000/docs**
- It starts with a built-in **Demo Hall** building, so the full loop works before the real photos exist.
- For Sakshi on the same Wi-Fi: find your IP with `ipconfig getifaddr en0` and send her `http://<that-ip>:8000`.
  (Campus Wi-Fi sometimes blocks this; if so, use the Vultr server from step 8.)
- Tests: `.venv/bin/python -m pytest -q`

Fresh machine? Create the environment first:
`python3.12 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt`

## 7. Tiger Data (optional — first thing to cut if late)

1. Sign up at **https://www.tigerdata.com** (Start for free).
2. In Tiger Console, click **New service** → choose **Shared** (the free option) → pick a US-East region → **Create**.
3. **Save the password / download the config file now** — it's only shown once.
4. Open the service → **Connect** → copy the **service URL** (looks like
   `postgres://tsdbadmin:PASSWORD@abc123.xyz.tsdb.cloud.timescale.com:34567/tsdb?sslmode=require`).
5. Put it in `.env` as `DATABASE_URL=...`
6. `scripts/check_keys.py` → `PASS Tiger Data`. The table `window_events` is created automatically.
7. See logged rows at **http://localhost:8000/api/log** (or in the console's SQL editor:
   `SELECT * FROM window_events ORDER BY time DESC LIMIT 20;`).

## 8. Vultr server (deploy, Task 10)

1. Claim credits at **mlh.link/vultr** and create a Vultr account.
2. Make an SSH key on your Mac (skip if `~/.ssh/id_ed25519.pub` exists):
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
   pbcopy < ~/.ssh/id_ed25519.pub     # copies the public key
   ```
3. Vultr → **Account → SSH Keys → Add SSH Key** → paste.
4. **Deploy → Cloud Compute → Shared CPU** → a US region (e.g. New Jersey or Chicago) → image **Ubuntu 24.04** →
   the cheapest plan (1 GB RAM is enough) → tick your SSH key → **Deploy**.
5. Wait for "Running" and copy the server's **IP address**.
6. From the `LightsOutAI` folder on your laptop (copies code + `.env`, installs, starts):
   ```bash
   deploy/push.sh <server-ip>
   ```
7. Test from your **phone on mobile data** (not campus Wi-Fi): `http://<server-ip>/api/health` and `http://<server-ip>/docs`.
   Sakshi's `frontend/` folder is served at `http://<server-ip>/`.
8. After any code change, run `deploy/push.sh <server-ip>` again.
   Logs if something breaks: `ssh root@<server-ip> journalctl -u lightsout -n 50`

## 9. Domain (Sakshi, optional)

1. Get the free domain at **mlh.link/GoDaddyRegistry**.
2. In the domain's **DNS** settings, add an **A record**: Host `@`, Points to `<server-ip>`, TTL lowest. (Optionally another A record for `www`.)
3. Wait a few minutes, then run `deploy/push.sh <server-ip> yourdomain.xyz` — this turns on **HTTPS** automatically.
4. Open `https://yourdomain.xyz/docs`.
   If you use HTTPS, the twin page must connect to `wss://yourdomain.xyz/ws` (not `ws://`).

## 10. Night photos → demo buildings (Task 8, after Sakshi's shoot)

1. Sakshi puts the photos in `photos/` (iPhone HEIC → JPG: `sips -s format jpeg IMG.HEIC --out IMG.jpg`).
2. Try thresholds:
   ```bash
   cd backend && .venv/bin/python scripts/run_photos.py tune
   ```
   Open `backend/output/tuning/` and pick the threshold whose boxes best match the lit windows.
3. Save the 2 best buildings:
   ```bash
   .venv/bin/python scripts/run_photos.py save "Davis Hall" ../photos/davis_1910.jpg --threshold 190
   ```
   If detection is messy, use the grid fallback (4 facade corners in pixels — read them off in Preview with the
   inspector, ⌘I): `--corners "[[x,y],[x,y],[x,y],[x,y]]" --floors 6 --cols 12`
4. Restart the server: saved buildings load automatically. Switch with `POST /api/select`.
