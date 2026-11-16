# Play Haus Phase 2 — odds comparison (beta)

This is **not** an automatic recommendation engine. It is a read-only, licensed-odds ingestion and comparison step. No picks are fabricated.

## Upload safely
1. Back up your GitHub repository. Your uploaded `index(1).html` was treated as the latest and saved here as `index.html` with one link added. Review differences before overwriting anything.
2. Add `fetch_odds.py`, `odds.html` to repository root; update root `index.html` only if that is the Pages entry point. If your site uses `docs/`, put website files and JSON in `docs/` and adjust output paths in the workflow accordingly.
3. Replace `.github/workflows/refresh.yml` with the supplied `refresh.yml` (do not put it in the root).
4. Obtain an API key from https://the-odds-api.com/ and verify your subscription covers US bookmaker odds, the requested sports, and player prop markets. Product availability and credit cost vary.
5. In GitHub: Settings → Secrets and variables → Actions → New repository secret. Name: `ODDS_API_KEY`. Never paste this key into HTML or commits.
6. Run Actions → Daily stats refresh + deploy → Run workflow. Open `odds.html` on the deployed site and inspect `odds_snapshot.json` status and timestamp.

## Data providers
- The Odds API: sportsbook odds via `/v4/sports/{sport}/odds/`; event props via `/v4/sports/{sport}/events/{eventId}/odds/`. Requires a key; coverage and rate limits depend on plan. Confirm market keys and subscription before production.
- PrizePicks: NOT connected. Obtain explicit permission or a licensed redistribution feed. Do not rely on scraping or undocumented endpoints. PrizePicks projections and sportsbook odds have different payout mechanics and should not be compared as if prices were identical.

## Operational limitations
- GitHub Actions runs twice daily, so this is not real-time. The page warns when snapshots exceed three hours. More frequent refreshes consume API credits.
- The event prop fetch is capped at 4 events per sport per run; expand carefully after checking usage.
- `odds_snapshot.json` is public by design; the API key stays server-side in GitHub Actions.
- Failed/unsupported markets are skipped with logged warnings; missing lines are not replaced with guesses.
- No calibrated probability model, automatic picks, backtest, grading, or historical recommendation tracking is included in this phase.
- `fetch_odds.py` uses standard library only. Test against your plan and actual responses before trusting output.
