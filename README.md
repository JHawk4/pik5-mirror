# pik5-mirror

An unofficial mirror of the Pikmin challenge-mode leaderboards on
[pik5.net](https://pik5.net/en/), shown as a clean, table-first records site
with per-board record history.

All record data belongs to pik5.net and its community. Every page credits
pik5 and links back to the original board.

## How it works

- `sync/pik5_sync.py` fetches pik5's page data (Next.js JSON at
  `/_next/data/<buildId>/en/...`) for every category and stage board, about 400
  requests at 1 per second. Only paths allowed by pik5's robots.txt are used.
  Output goes to `data/`:
  - `categories.json`, `stages.json`, `users.json`, `meta.json`
  - `boards/<rule>-<stage>.json`: current leaderboard
  - `totals/<id>.json`: overall rankings
  - `history/<rule>-<stage>.json`: record progression, extended on every sync
- `python sync/pik5_sync.py backfill [rule ...]` rebuilds past record history
  from pik5's year-end snapshots. It costs about 20 requests per board
  (~7,500 for everything), so run it sparingly or per category.
  - `archive/<rule>-<stage>.json`: every submission ever seen, used to rebuild
    leaderboards as of any date
  - `players.json`: speedrun.com name and country for notable players
    (`python sync/pik5_sync.py players` refreshes these alone)
  - `src_runners.json`: every runner on speedrun.com's Pikmin series boards with
    their country (`python sync/pik5_sync.py src`, run daily by the workflow);
    the build matches pik5 players to these by name for flags and English names
- `site/build.py` renders `data/` into a static site in `dist/` with no
  dependencies: `dist/en/` and `dist/ja/`, with `dist/index.html` picking a
  language from the browser.
  - `site/i18n.py`: all UI text in English and Japanese
  - `site/players_overrides.json`: hand-made English nicknames and countries
  - `site/score_meta.py`: how scores turn into time used / time left
    (Pikmin 3 bonus rates per stage, Pikmin 4 1 point/second, Sage Leaf time
    limits), with sources. Tables show Score, Time used and Time left as
    separate right-aligned columns (bold = the board's ranking measure); time
    columns are left out of tables where no row has a time.
- `.github/workflows/sync.yml` syncs every 6 hours, commits data changes and
  deploys to GitHub Pages.

## Local use

```bash
python sync/pik5_sync.py
python site/build.py
python -m http.server -d dist 8000
```
