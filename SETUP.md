# Play Haus: activate sportsbook odds (Step 2)

Your GitHub Actions secret must already be named `ODDS_API_KEY`.

1. Upload `fetch_odds.py` to the repository **root**, alongside `build_data.py`.
2. Upload `.github/workflows/refresh.yml` to the exact path shown, replacing the existing workflow **after making a backup**. Do not upload the workflow to the root.
3. Commit both files to the `main` branch.
4. In GitHub, open **Actions → Daily stats refresh + deploy → Run workflow**.
5. Expand the **Fetch sportsbook odds and player props** step. It should print `Odds status: ... games: ... prop events: ... errors: ...`.
6. Check `https://playhausbets.github.io/playhaus/odds_snapshot.json` after successful deployment. It should have an `updated` timestamp and `games` / `props` arrays.

Important: The snapshot is read-only sportsbook market data, **not PrizePicks lines and not model recommendations**. It will not automatically fill `haus_picks.json`. Event props are capped at four events per sport to limit API credits. Some plans do not cover all markets; inspect warnings. The original website is left unchanged in this package.

If status is `unavailable`, inspect the warnings and verify your Odds API subscription/market availability. If status is `not_configured`, verify the secret is named `ODDS_API_KEY` in the correct repository.

Do not commit the API key, and do not paste it into HTML or chat. The widget `accessKey` is different.
