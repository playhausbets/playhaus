# 💸 Play Haus

NBA & NFL player-prop research tool: daily projections, ceilings, matchups, player lab with simulation, lineup builder, slip generator and results tracker.
Runs entirely in the browser — no server, no accounts. Stats, schedules and injuries refresh automatically every morning.

## Set it up (one time, ~10 minutes)

1. **Create the repo.** On github.com tap **+ → New repository**. Name it `playhaus`, set it to **Public**, and create it (leave "Add a README" unchecked).
2. **Add these files.** Upload everything in this folder, keeping the folders (`docs/`, `scripts/`, `.github/workflows/`). On a computer you can drag the whole folder onto the repo page.
3. **Turn on Pages.** Repo → **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. **Run it once.** Repo → **Actions → "Daily stats refresh + deploy" → Run workflow**. In about 2–3 minutes your site is live at
   `https://YOUR-USERNAME.github.io/playhaus/`
   (the exact link shows on the finished run and under Settings → Pages).

After that it rebuilds itself every morning. If a refresh ever fails, the site keeps yesterday's data and GitHub emails you.

## Custom domain (optional, ~$12/yr)

Buy a domain (e.g. from Cloudflare, Namecheap, or Porkbun). In the repo go to **Settings → Pages → Custom domain**, enter it, and follow GitHub's DNS instructions (add the records it shows at your domain registrar). Tick **Enforce HTTPS** once it's available.

## What's in here

| Path | What it does |
|---|---|
| `docs/index.html` | The whole app |
| `docs/data.json`, `docs/slate.json` | Stats (5 seasons, active players), upcoming games, odds, injuries — rebuilt daily |
| `scripts/build_data.py` | Downloads public data and builds the two JSON files |
| `.github/workflows/refresh.yml` | Runs the build every morning and publishes the site |

## Data sources
- NBA box scores & schedule: [sportsdataverse/hoopR-nba-data](https://github.com/sportsdataverse/hoopR-nba-data) (originally ESPN)
- NFL stats, injuries, schedule & lines: [nflverse](https://github.com/nflverse)

If you ever charge for access, check these sources' terms first — the NBA data originates from ESPN.

## Notes
- Visitors' tracker history, bankroll and settings are saved in their own browser only.
- Screenshot reading is only available in the Claude version; here, upload a CSV/Excel lines file.
- For research and entertainment. 21+. Not affiliated with PrizePicks or any sportsbook. Problem gambling help: 1-800-GAMBLER.
