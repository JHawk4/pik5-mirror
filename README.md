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
- `site/build.py` renders `data/` into a static site in `dist/` with no
  dependencies.
- `.github/workflows/sync.yml` syncs every 6 hours, commits data changes and
  deploys to GitHub Pages.

## Local use

```bash
python sync/pik5_sync.py
python site/build.py
python -m http.server -d dist 8000
```
