# pikmin-wrs notes for agents

- The user wants every finished change committed and pushed right away, without asking first
  (pull --rebase before pushing; pushing to main redeploys the live site at https://jhawk4.github.io/pikmin-wrs/).

- Visitor suggestions from the site go to a Google Form owned by the user.
  Read them at https://docs.google.com/forms/d/1gSumsqRO9tE9dbLnjvyxNl2puufcHhAgVOtZUkaRVm0/edit#responses
  (needs the user's Google sign-in; use Claude in Chrome, keeping the window in front). Details in README.md → Suggestions.
- Repo: github.com/JHawk4/pikmin-wrs (public; GitHub Pages serves dist/ via the workflow). For `gh` on this repo, prefix commands with
  `GH_TOKEN=$(gh auth token -h github.com -u JHawk4)`; plain git push/pull already uses the JHawk4 login.
- The GitHub Actions workflow syncs pik5.net every 6 hours and commits to `data/`, so pull before pushing.
- Be polite to pik5.net: keep requests serialized with a delay (see sync/pik5_sync.py); robots.txt disallows /api/.
- Curated data that does not sync on its own: site/tas.json (TAS records), site/players_overrides.json (English names, countries),
  site/score_meta.py (score-to-time rules).
