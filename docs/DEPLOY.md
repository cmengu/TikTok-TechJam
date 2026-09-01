# Deploying the dashboard to Vercel (read-only snapshot viewer)

1. On vercel.com: Add New > Project, import `cmengu/TikTok-TechJam`.
2. Framework preset "Other"; leave build command, output dir, and env vars empty; Deploy.
3. Every push to `main` redeploys automatically; live runs only appear on the site after their `runs/<id>/` records are committed and pushed.

Locally nothing changes: `python -m uvicorn app.server:app` still serves the live-tailing dashboard.
