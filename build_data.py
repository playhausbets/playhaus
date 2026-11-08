"""Pick Bot data builder. Writes data.json (5 seasons of game logs) and slate.json (upcoming games, odds, injuries).
Sources: sportsdataverse/hoopr-nba-data (NBA box scores + schedule), nflverse (NFL weekly stats, injuries, schedule with lines).
Usage: python3 build_data.py OUT_DIR  (expects the source files already downloaded; see fetch() for paths)."""
import json, os, sys, base64, subprocess, datetime as dt
import numpy as np, pandas as pd

W = os.environ.get("PB_WORK", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".work"))
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
NBA_REPO, NFLD_REPO, RAW = f"{W}/sportsdataverse/hoopr-nba-data", f"{W}/nflverse/nfldata", f"{W}/data/raw"
ET = "America/New_York"
TODAY = pd.Timestamp.now(tz=ET).date()
NBA_SEASON = TODAY.year + 1 if TODAY.month >= 8 else TODAY.year      # hoopR labels 2026-27 as 2027
NFL_SEASON = TODAY.year if TODAY.month >= 6 else TODAY.year - 1
NBA_YEARS = list(range(NBA_SEASON - 4, NBA_SEASON + 1))
NFL_YEARS = list(range(NFL_SEASON - 4, NFL_SEASON + 1))
NFL_ALIAS = {"LA": "LAR", "WSH": "WAS", "JAC": "JAX", "OAK": "LV", "SD": "LAC", "STL": "LAR"}

def sh(cmd): subprocess.run(cmd, shell=True, check=True)

def espn_json(path):
    import urllib.request
    try:
        req = urllib.request.Request("https://site.api.espn.com/apis/site/v2/sports/" + path, headers={"User-Agent": "Mozilla/5.0 (PlayHaus data refresh)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("ESPN skipped:", path.split("?")[0], type(e).__name__)
        return None

def _ml(x):
    try:
        if isinstance(x, dict):
            for k in ("close", "current", "open"):
                if k in x and isinstance(x[k], dict) and x[k].get("odds") not in (None, ""):
                    return _ml(x[k]["odds"])
            return None
        if x in (None, "", "EVEN", "even"): return 100 if x in ("EVEN", "even") else None
        return int(float(str(x).replace("+", "")))
    except Exception:
        return None

def espn_lines(sport_path, days):
    """{(date, home, away): {total, spread(home), ml_home, ml_away}} from ESPN scoreboards."""
    import re
    out = {}
    for d in days:
        js = espn_json(f"{sport_path}/scoreboard?dates={d.strftime('%Y%m%d')}")
        if not js: break
        for ev in js.get("events", []):
            try:
                comp = ev["competitions"][0]
                side = {c["homeAway"]: c["team"]["abbreviation"] for c in comp["competitors"]}
                local = pd.Timestamp(ev["date"]).tz_convert(ET)
                odds = (comp.get("odds") or [{}])[0]
                total = odds.get("overUnder"); spread = None
                det = str(odds.get("details") or "")
                m = re.match(r"([A-Z]{2,4})\s+([-+]?\d+(?:\.\d+)?)", det)
                if m: spread = float(m.group(2)) if m.group(1) == side["home"] else -float(m.group(2))
                elif det.upper().startswith("EVEN"): spread = 0.0
                elif odds.get("spread") is not None: spread = float(odds["spread"])
                mlh = _ml((odds.get("homeTeamOdds") or {}).get("moneyLine")); mla = _ml((odds.get("awayTeamOdds") or {}).get("moneyLine"))
                if mlh is None and isinstance(odds.get("moneyline"), dict):
                    mlh = _ml(odds["moneyline"].get("home")); mla = _ml(odds["moneyline"].get("away"))
                out[(str(local.date()), side["home"], side["away"])] = {"total": None if total is None else float(total), "spread": spread, "ml_home": mlh, "ml_away": mla}
            except Exception:
                continue
    return out

def fetch():
    os.makedirs(RAW, exist_ok=True)
    if not os.path.isdir(NBA_REPO + "/.git"):
        sh(f"GIT_LFS_SKIP_SMUDGE=1 git clone -q --depth 1 --filter=blob:none --no-checkout https://github.com/sportsdataverse/hoopr-nba-data {NBA_REPO}")
    pats = " ".join([f"/nba/player_box/parquet/player_box_{y}.parquet" for y in NBA_YEARS] + [f"/nba/schedules/parquet/nba_schedule_{NBA_SEASON}.parquet"])
    sh(f"cd {NBA_REPO} && git fetch -q --depth 1 origin main && git sparse-checkout set --no-cone {pats} && git checkout -q -B main origin/main")
    if not os.path.isdir(NFLD_REPO + "/.git"):
        sh(f"GIT_LFS_SKIP_SMUDGE=1 git clone -q --depth 1 --filter=blob:none --no-checkout https://github.com/nflverse/nfldata {NFLD_REPO}")
    sh(f"cd {NFLD_REPO} && git fetch -q --depth 1 origin master && git sparse-checkout set --no-cone /data/games.csv && git checkout -q -B master origin/master")
    rel = "https://github.com/nflverse/nflverse-data/releases/download"
    for y in NFL_YEARS:
        f = f"{RAW}/nfl_{y}.csv"
        if y < NFL_SEASON and os.path.exists(f) and os.path.getsize(f) > 1000: continue
        url = f"{rel}/stats_player/stats_player_week_{y}.csv" if y >= 2025 else f"{rel}/player_stats/player_stats_{y}.csv"
        sh(f"curl -sSLf --max-time 180 -o {f} {url}")
    sh(f"curl -sSLf --max-time 120 -o {RAW}/nfl_inj_{NFL_SEASON}.csv {rel}/injuries/injuries_{NFL_SEASON}.csv || true")

def nba():
    d = pd.concat([pd.read_parquet(f"{NBA_REPO}/nba/player_box/parquet/player_box_{y}.parquet") for y in NBA_YEARS], ignore_index=True)
    d = d[d.season_type.isin([2, 3])]
    vc = d.team_abbreviation.value_counts(); real = set(vc[vc > 500].index)
    d = d[d.team_abbreviation.isin(real) & d.opponent_team_abbreviation.isin(real)].copy()
    played = d[(~d.did_not_play.fillna(False)) & (d.minutes.fillna(0) > 0)].dropna(subset=["points"]).copy()
    played["date"] = pd.to_datetime(played.game_date).dt.strftime("%Y%m%d").astype(int)
    played = played.sort_values(["date", "game_id"])
    tm = played.groupby(["game_id", "team_abbreviation"])[["field_goals_attempted", "free_throws_attempted", "turnovers", "minutes", "offensive_rebounds", "points"]].sum()
    tm.columns = ["tfga", "tfta", "ttov", "tmin", "toreb", "tpts"]
    played = played.join(tm, on=["game_id", "team_abbreviation"])
    num_ = played.field_goals_attempted.fillna(0) + 0.44 * played.free_throws_attempted.fillna(0) + played.turnovers.fillna(0)
    den_ = played.minutes * (played.tfga + 0.44 * played.tfta + played.ttov)
    played["usg"] = (100 * num_ * (played.tmin / 5) / den_).clip(0, 99).fillna(0)
    # team pace / scoring (this season, fallback last season)
    tgm = tm.reset_index().merge(played[["game_id", "season"]].drop_duplicates(), on="game_id")
    tgm["poss"] = tgm.tfga + 0.44 * tgm.tfta - tgm.toreb + tgm.ttov
    opp = tgm[["game_id", "team_abbreviation", "tpts", "poss"]].rename(columns={"team_abbreviation": "opp", "tpts": "opts", "poss": "oposs"})
    tgm = tgm.merge(opp, on="game_id"); tgm = tgm[tgm.team_abbreviation != tgm.opp]
    tstats = {}
    for t, g_ in tgm.groupby("team_abbreviation"):
        cur_ = g_[g_.season == NBA_SEASON]; g2 = cur_ if len(cur_) >= 3 else g_[g_.season == NBA_SEASON - 1]
        if len(g2): tstats[t] = {"g": int(len(cur_)), "pace": round(float(((g2.poss + g2.oposs) / 2).mean()), 1), "pf": round(float(g2.tpts.mean()), 1), "pa": round(float(g2.opts.mean()), 1)}
    active = set(played[played.season >= NBA_SEASON - 1].athlete_id)   # only players active this season or last
    played = played[played.athlete_id.isin(active)]
    teams = sorted(real); tix = {t: i for i, t in enumerate(teams)}
    tinfo = {r.team_abbreviation: [r.team_name, r.team_location, r.team_display_name]
             for r in played.drop_duplicates("team_abbreviation").itertuples()}
    pl = played.groupby("athlete_id").tail(1); pix = {p: i for i, p in enumerate(pl.athlete_id)}
    players = [[r.athlete_display_name, r.athlete_position_abbreviation or ""] for r in pl.itertuples()]
    num = lambda c: [int(round(x)) for x in played[c].fillna(0)]
    base = dt.date(2022, 1, 1)
    days = lambda s: [(dt.date(x // 10000, x // 100 % 100, x % 100) - base).days for x in s]
    cols = {"p": [pix[x] for x in played.athlete_id], "d": days(played.date), "s": played.season.astype(int).tolist(),
            "t": [tix[x] for x in played.team_abbreviation], "o": [tix[x] for x in played.opponent_team_abbreviation],
            "h": [1 if x == "home" else 0 for x in played.home_away], "st": [1 if x else 0 for x in played.starter.fillna(False)],
            "min": num("minutes"), "pts": num("points"), "reb": num("rebounds"), "ast": num("assists"), "stl": num("steals"),
            "blk": num("blocks"), "tov": num("turnovers"), "fgm": num("field_goals_made"), "fga": num("field_goals_attempted"),
            "fg3m": num("three_point_field_goals_made"), "fg3a": num("three_point_field_goals_attempted"), "ftm": num("free_throws_made"), "fta": num("free_throws_attempted"), "usg": num("usg"),
            "oreb": num("offensive_rebounds"), "dreb": num("defensive_rebounds")}
    g = played[played.season >= NBA_SEASON - 1].drop_duplicates("game_id")
    league_total = float((g.team_score + g.opponent_team_score).mean())
    # schedule (upcoming 4 days)
    sc = pd.read_parquet(f"{NBA_REPO}/nba/schedules/parquet/nba_schedule_{NBA_SEASON}.parquet")
    sc["local"] = pd.to_datetime(sc.date, utc=True).dt.tz_convert(ET)
    up = sc[(sc.local.dt.date >= TODAY) & (sc.local.dt.date <= TODAY + dt.timedelta(days=4))]
    lines = espn_lines("basketball/nba", [TODAY + dt.timedelta(days=k) for k in range(5)])
    games = []
    for r in up.itertuples():
        if r.home_abbreviation not in tix or r.away_abbreviation not in tix: continue
        ln = lines.get((str(r.local.date()), r.home_abbreviation, r.away_abbreviation), {})
        games.append({"day": (r.local.date() - base).days, "date": str(r.local.date()), "time": r.local.strftime("%-I:%M %p"),
                      "home": r.home_abbreviation, "away": r.away_abbreviation, "total": ln.get("total"), "spread": ln.get("spread"),
                      "ml_home": ln.get("ml_home"), "ml_away": ln.get("ml_away")})
    print("NBA games with lines:", sum(1 for g_ in games if g_["total"] is not None), "of", len(games))
    # auto injury signal: rotation players who missed their team's most recent games
    inj = []
    ij = espn_json("basketball/nba/injuries")
    if ij and ij.get("injuries"):
        name2ab = {}
        for ab, info in tinfo.items():
            for nm in info: name2ab[str(nm).lower()] = ab
        for team in ij["injuries"]:
            ab = name2ab.get(str(team.get("displayName", "")).lower())
            for it in team.get("injuries", []):
                ath = it.get("athlete") or {}; st = str(it.get("status") or "").lower()
                status = "out" if "out" in st else "doubtful" if "doubt" in st else "questionable" if st else ""
                if not status or not ath.get("displayName"): continue
                ab2 = ((ath.get("team") or {}).get("abbreviation")) or ab or ""
                inj.append({"name": ath["displayName"], "team": ab2, "status": status, "why": "ESPN: " + (it.get("shortComment") or it.get("status") or "")[:90], "auto": True})
        print("NBA injuries from ESPN:", len(inj))
    cur = d[d.season == NBA_SEASON].copy(); cur["dn"] = pd.to_datetime(cur.game_date)
    rot = played[played.season == NBA_SEASON].groupby("athlete_id").agg(mins=("minutes", "mean"), gp=("minutes", "size"))
    rot = rot[(rot.mins >= 20) & (rot.gp >= 3)]
    for team, tg in ([] if inj else cur.groupby("team_abbreviation")):
        last_games = sorted(tg.game_id.unique(), key=lambda x: tg[tg.game_id == x].dn.iloc[0])[-2:]
        for pid in rot.index:
            prow = played[(played.athlete_id == pid) & (played.season == NBA_SEASON)]
            if prow.empty or prow.team_abbreviation.iloc[-1] != team: continue
            missed = [gid for gid in last_games if not ((prow.game_id == gid).any())]
            if not missed: continue
            why = tg[(tg.athlete_id == pid) & (tg.game_id == last_games[-1])].reason
            reason = (why.iloc[0] if len(why) else "") or ""
            if len(missed) == 2 or (last_games[-1] in missed and reason and "COACH" not in reason):
                inj.append({"name": prow.athlete_display_name.iloc[-1], "team": team,
                            "status": "out" if len(missed) == 2 else "questionable",
                            "why": f"missed last {len(missed)} game{'s' if len(missed) > 1 else ''}" + (f" ({reason.title()})" if reason and "COACH" not in reason else ""),
                            "auto": True})
    return ({"players": players, "teams": teams, "teamInfo": tinfo, "cols": cols, "dateBase": "2022-01-01",
             "through": str(played.date.max()), "leagueTotal": round(league_total, 1), "teamStats": tstats,
             "teamColor": {r.team_abbreviation: "#" + str(r.team_color) for r in played.drop_duplicates("team_abbreviation").itertuples() if isinstance(r.team_color, str)},
             "n": len(played)},
            {"games": games, "injuries": inj})

def nfl():
    gm = pd.read_csv(f"{NFLD_REPO}/data/games.csv")
    gm["home_team"] = gm.home_team.replace(NFL_ALIAS); gm["away_team"] = gm.away_team.replace(NFL_ALIAS)
    homes = set(zip(gm.season, gm.week, gm.home_team))
    fr = []
    for y in NFL_YEARS:
        f = pd.read_csv(f"{RAW}/nfl_{y}.csv", low_memory=False)
        f = f.rename(columns={"recent_team": "team", "interceptions": "passing_interceptions"})
        fr.append(f)
    d = pd.concat(fr, ignore_index=True)
    d = d[d.position.isin(["QB", "RB", "WR", "TE", "FB"]) & d.season_type.isin(["REG", "POST"])].copy()
    d["team"] = d.team.replace(NFL_ALIAS); d["opponent_team"] = d.opponent_team.replace(NFL_ALIAS)
    d["key"] = d.season.astype(int) * 100 + d.week.astype(int)
    d = d.sort_values("key")
    active = set(d[d.season >= NFL_SEASON - 1].player_id)                # only players active this season or last
    d = d[d.player_id.isin(active)]
    teams = sorted(set(d.team) | set(d.opponent_team)); tix = {t: i for i, t in enumerate(teams)}
    pl = d.groupby("player_id").tail(1); pix = {p: i for i, p in enumerate(pl.player_id)}
    players = [[r.player_display_name, r.position] for r in pl.itertuples()]
    num = lambda c: [int(round(x)) for x in d[c].fillna(0)]
    cols = {"p": [pix[x] for x in d.player_id], "d": d.key.tolist(), "s": d.season.astype(int).tolist(),
            "t": [tix[x] for x in d.team], "o": [tix[x] for x in d.opponent_team],
            "h": [1 if (s, w, t) in homes else 0 for s, w, t in zip(d.season, d.week, d.team)],
            "pyd": num("passing_yards"), "ptd": num("passing_tds"), "patt": num("attempts"), "cmp": num("completions"),
            "int": num("passing_interceptions"), "ryd": num("rushing_yards"), "ratt": num("carries"), "rtd": num("rushing_tds"),
            "rec": num("receptions"), "recyd": num("receiving_yards"), "tgt": num("targets"), "rectd": num("receiving_tds"),
            "fp10": [int(round(x * 10)) for x in d.fantasy_points_ppr.fillna(0)]}
    # historical game environment per (key, team) for backtests: total, team spread (negative = favored)
    env = {}
    for r in gm[gm.season >= NFL_YEARS[0]].itertuples():
        if pd.isna(r.total_line): continue
        k = int(r.season) * 100 + int(r.week)
        env[f"{k}|{r.home_team}"] = [float(r.total_line), -float(r.spread_line)]
        env[f"{k}|{r.away_team}"] = [float(r.total_line), float(r.spread_line)]
    lt = float(gm[(gm.season >= NFL_SEASON - 1) & gm.total_line.notna()].total_line.mean())
    done = gm[(gm.season == NFL_SEASON) & gm.home_score.notna()]
    rows_ = pd.concat([pd.DataFrame({"t": done.home_team, "pf": done.home_score, "pa": done.away_score}), pd.DataFrame({"t": done.away_team, "pf": done.away_score, "pa": done.home_score})])
    tstats = {t: {"g": int(len(x)), "pf": round(float(x.pf.mean()), 1), "pa": round(float(x.pa.mean()), 1)} for t, x in rows_.groupby("t")}
    gm["gd"] = pd.to_datetime(gm.gameday).dt.date
    up = gm[(gm.gd >= TODAY) & (gm.gd <= TODAY + dt.timedelta(days=8)) & (gm.season == NFL_SEASON)]
    def t12(x):
        try: h, m = str(x).split(":")[:2]; h = int(h); return f"{(h - 1) % 12 + 1}:{m} {'PM' if h >= 12 else 'AM'}"
        except Exception: return ""
    nint = lambda v: None if pd.isna(v) else int(v)
    games = [{"key": int(r.season) * 100 + int(r.week), "date": str(r.gd), "time": t12(r.gametime), "home": r.home_team, "away": r.away_team,
              "total": None if pd.isna(r.total_line) else float(r.total_line),
              "spread": None if pd.isna(r.spread_line) else -float(r.spread_line),
              "ml_home": nint(r.home_moneyline), "ml_away": nint(r.away_moneyline)} for r in up.sort_values(["gd", "gametime"]).itertuples()]
    inj = []
    fi = f"{RAW}/nfl_inj_{NFL_SEASON}.csv"
    if os.path.exists(fi) and os.path.getsize(fi) > 100 and games:
        ij = pd.read_csv(fi, low_memory=False); ij["team"] = ij.team.replace(NFL_ALIAS)
        nextwk = {}
        for g in games:
            for t in (g["home"], g["away"]): nextwk.setdefault(t, g["key"] % 100)
        ij = ij[ij.season == NFL_SEASON]
        for r in ij.itertuples():
            if nextwk.get(r.team) != r.week or not isinstance(r.report_status, str): continue
            inj.append({"name": r.full_name, "team": r.team, "status": r.report_status.lower(),
                        "why": str(r.report_primary_injury) if isinstance(r.report_primary_injury, str) else "", "auto": True})
    return ({"players": players, "teams": teams, "cols": cols, "env": env, "leagueTotal": round(lt, 1), "teamStats": tstats,
             "through": f"{d.key.max() // 100} week {d.key.max() % 100}", "n": len(d)},
            {"games": games, "injuries": inj})

def pack(block, nba_dates=False):
    out = {}
    for k, v in block["cols"].items():
        a = np.asarray(v, dtype=np.int64)
        for t, dtp, lo, hi in (("u8", "<u1", 0, 255), ("u16", "<u2", 0, 65535), ("i16", "<i2", -32768, 32767), ("i32", "<i4", -2**31, 2**31 - 1)):
            if a.min() >= lo and a.max() <= hi: break
        out[k] = [t, base64.b64encode(a.astype(dtp).tobytes()).decode()]
    block["cols"] = out

if __name__ == "__main__":
    if "--no-fetch" not in sys.argv: fetch()
    nb, nbs = nba(); nf, nfs = nfl()
    pack(nb); pack(nf)
    os.makedirs(OUT, exist_ok=True)
    stamp = pd.Timestamp.now(tz=ET).strftime("%Y-%m-%d %H:%M")
    json.dump({"built": stamp, "NBA": nb, "NFL": nf}, open(f"{OUT}/data.json", "w"), separators=(",", ":"))
    json.dump({"built": stamp, "today": str(TODAY), "NBA": nbs, "NFL": nfs}, open(f"{OUT}/slate.json", "w"), separators=(",", ":"))
    print("data.json", os.path.getsize(f"{OUT}/data.json") // 1024, "KB | NBA", nb["n"], "rows thru", nb["through"],
          "| NFL", nf["n"], "rows thru", nf["through"], "| upcoming NBA", len(nbs["games"]), "NFL", len(nfs["games"]),
          "| auto injuries NBA", len(nbs["injuries"]), "NFL", len(nfs["injuries"]))
