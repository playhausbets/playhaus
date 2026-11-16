"""Optional licensed sportsbook odds snapshot. Never expose API keys in the browser."""
import json, os, sys, datetime, urllib.request, urllib.parse, urllib.error
from pathlib import Path

BASE = 'https://api.the-odds-api.com/v4/sports'
SPORTS = {'basketball_nba':'NBA','americanfootball_nfl':'NFL','basketball_ncaab':'CBB','basketball_wnba':'WNBA'}
MARKETS = 'h2h,spreads,totals'
PROP_MARKETS = {'basketball_nba':'player_points,player_rebounds,player_assists',
                'americanfootball_nfl':'player_pass_yds,player_rush_yds,player_reception_yds'}
MAX_EVENTS = int(os.getenv('ODDS_MAX_PROP_EVENTS','4'))

def request(path, params):
    query=urllib.parse.urlencode({**params,'apiKey':os.environ['ODDS_API_KEY']})
    req=urllib.request.Request(BASE+path+'?'+query,headers={'User-Agent':'PlayHaus-Research/1.0'})
    with urllib.request.urlopen(req,timeout=25) as r:
        return json.load(r)

def normalize(game, league, market_group):
    books=[]
    for b in game.get('bookmakers',[]):
        markets=[]
        for m in b.get('markets',[]):
            markets.append({'key':m.get('key'),'last_update':m.get('last_update'),
                'outcomes':[{'name':o.get('name'),'description':o.get('description'),
                             'price':o.get('price'),'point':o.get('point')} for o in m.get('outcomes',[])]})
        if markets:books.append({'key':b.get('key'),'title':b.get('title'),'markets':markets})
    return {'id':game.get('id'),'league':league,'home_team':game.get('home_team'),
        'away_team':game.get('away_team'),'commence_time':game.get('commence_time'),
        'group':market_group,'bookmakers':books}

def main():
    out=Path(sys.argv[1] if len(sys.argv)>1 else '.')
    output={'updated':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source':'The Odds API (licensed key required)','status':'not_configured',
            'games':[],'props':[],'errors':[],'prizepicks':{'status':'not_connected','message':'Requires a permitted licensed feed or approved integration.'}}
    if not os.getenv('ODDS_API_KEY'):
        output['errors'].append('ODDS_API_KEY not configured; no sportsbook data fetched.')
    else:
        output['status']='partial'
        for sport,league in SPORTS.items():
            try:
                games=request('/'+sport+'/odds/',{'regions':os.getenv('ODDS_REGIONS','us'), 'markets':MARKETS,'oddsFormat':'american','dateFormat':'iso'})
                output['games'] += [normalize(g,league,'game') for g in games]
                # Event-level props require a supported subscription/market. Restrict calls to conserve credits.
                for g in games[:MAX_EVENTS] if sport in PROP_MARKETS else []:
                    try:
                        props=request('/'+sport+'/events/'+g['id']+'/odds/',{'regions':os.getenv('ODDS_REGIONS','us'),
                           'markets':PROP_MARKETS[sport],'oddsFormat':'american'})
                        output['props'].append(normalize(props,league,'props'))
                    except (urllib.error.HTTPError,urllib.error.URLError,ValueError) as e:
                        output['errors'].append(f'{league} props {g.get("id")}: {e}')
            except (urllib.error.HTTPError,urllib.error.URLError,ValueError) as e:
                output['errors'].append(f'{league} games: {e}')
        output['status']='ok' if output['games'] and not output['errors'] else ('partial' if output['games'] else 'unavailable')
    (out/'odds_snapshot.json').write_text(json.dumps(output,separators=(',',':')))
    print('Odds status:',output['status'],'games:',len(output['games']),'prop events:',len(output['props']),'errors:',len(output['errors']))
    for err in output['errors']:print('WARNING:',err)
if __name__=='__main__':main()
