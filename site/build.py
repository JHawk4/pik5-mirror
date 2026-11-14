"""Render the mirrored pik5 data in data/ as a static site in dist/.

Usage: python site/build.py
"""

from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
SRC = Path(__file__).resolve().parent

SERIES = {1: "Pikmin", 2: "Pikmin 2", 3: "Pikmin 3", 4: "Pikmin 4"}
SERIES_SLUG = {1: "pikmin1", 2: "pikmin2", 3: "pikmin3", 4: "pikmin4"}
CONSOLES = {1: "GC", 2: "Wii", 3: "Wii U", 4: "Switch", 5: "Switch 2", 7: "3DS", 12: "Wii U VC"}
PIK5 = "https://pik5.net/en"
NOW = datetime.now(timezone.utc)

e = html.escape


def load(name, default=None):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


# ---------------------------------------------------------------- data

meta = load("meta.json", {})
categories = load("categories.json", [])
stages = {int(k): v for k, v in load("stages.json", {}).items()}
users = load("users.json", {})


def board(rule, sid):
    return load(f"boards/{rule}-{sid}.json", {"posts": []})


def history(rule, sid):
    return load(f"history/{rule}-{sid}.json", {"records": []})


def parse_date(s):
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------- formatting

def mmss(sec):
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_score(score, st):
    """Format a score the way pik5 shows it. `st` is the stage info dict.
    - int: plain points
    - speedrun: elapsed seconds (lower is better)
    - time: seconds remaining; pik5 shows elapsed time (limit - remaining)
      when the stage has a time limit, otherwise the stored value"""
    if score is None:
        return ""
    st = st or {}
    display = st.get("display")
    if display == "speedrun":
        return mmss(score)
    if display == "time":
        limit = st.get("time") or 0
        return mmss(limit - score if limit else score)
    return f"{score:,}"


def fmt_date(s):
    d = parse_date(s)
    return d.strftime("%Y-%m-%d") if d else ""


def days_between(a, b):
    da, db = parse_date(a), parse_date(b) if isinstance(b, str) else b
    if not da or not db:
        return ""
    return str(max(0, (db - da).days))


def player_name(uid):
    return users.get(uid) or uid or "?"


def player_link(uid, pre):
    if not uid:
        return "?"
    return f'<a href="{pre}player/{quote(uid, safe="")}.html">{e(player_name(uid))}</a>'


def video_cell(p):
    v = (p.get("video") or "").strip()
    if not v:
        return ""
    if not v.startswith("http"):
        v = "https://www.youtube.com/watch?v=" + v
    return f'<a class="vid" href="{e(v)}" target="_blank" rel="noopener" title="Video">&#9654;</a>'


def score_cell(p, display):
    s = fmt_score(p.get("score"), display)
    v = (p.get("video") or "").strip()
    if v:
        if not v.startswith("http"):
            v = "https://www.youtube.com/watch?v=" + v
        return f'<a href="{e(v)}" target="_blank" rel="noopener" title="Watch video">{s}</a>'
    return s


def pik5_board_url(rule, sid):
    return f"{PIK5}/stage/{sid}" if rule == 48 else f"{PIK5}/stage/{sid}/0/{rule}"


def stage_name(sid):
    st = stages.get(sid) or {}
    return st.get("name") or f"Stage {sid}"


# ---------------------------------------------------------------- layout

def page(title, body, pre, active=None):
    nav = "".join(
        f'<a class="s{s}{" on" if active == s else ""}" href="{pre}{SERIES_SLUG[s]}.html">{SERIES[s]}</a>'
        for s in SERIES
    )
    synced = parse_date(meta.get("synced_at"))
    synced_txt = synced.strftime("%Y-%m-%d %H:%M UTC") if synced else "unknown"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · Pikmin Score Records</title>
<link rel="stylesheet" href="{pre}style.css">
</head>
<body>
<header class="top">
  <a class="brand" href="{pre}index.html">Pikmin Score Records</a>
  <nav>{nav}<a class="{'on' if active == 'players' else ''}" href="{pre}players.html">Players</a></nav>
</header>
<main>
{body}
</main>
<footer>
  All records are from <a href="https://pik5.net/en/">pik5.net</a>, the Pikmin challenge-mode ranking site, and belong to its community.
  This is an unofficial mirror. Last synced {synced_txt}.
</footer>
</body>
</html>
"""


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def write(rel, content):
    p = DIST / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------- pages

def current_wrs(rule, sid):
    b = board(rule, sid)
    return [p for p in b["posts"] if p.get("rank") == 1], b


def series_page(series):
    pre = ""
    cats = [c for c in categories if c["series"] == series]
    parts = [f"<h1>{SERIES[series]}</h1>"]
    toc = " · ".join(f'<a href="#c{c["rule"]}">{e(c["label"])}</a>' for c in cats)
    parts.append(f'<p class="toc">{toc}</p>')
    for kind, heading in (("main", "Main categories"), ("special", "Special categories")):
        group = [c for c in cats if c["kind"] == kind]
        if not group:
            continue
        parts.append(f"<h2 class='kind'>{heading}</h2>")
        for c in group:
            rows = []
            total = 0
            for sid in c["stages"]:
                wrs, b = current_wrs(c["rule"], sid)
                disp = stages.get(sid)
                link = f'<a href="stage/{c["rule"]}-{sid}.html">{e(stage_name(sid))}</a>'
                if not wrs:
                    rows.append([link, "—", "", "", "", ""])
                    continue
                wrs.sort(key=lambda p: p.get("date") or "")
                w = wrs[0]
                total += w.get("score") or 0
                if len(wrs) <= 3:
                    holders = ", ".join(player_link(p["user"], pre) for p in wrs)
                else:
                    others = ", ".join(player_name(p["user"]) for p in wrs[1:])
                    holders = (f'{player_link(w["user"], pre)} <a class="tie" title="{e(others)}" '
                               f'href="stage/{c["rule"]}-{sid}.html">+{len(wrs) - 1} tied</a>')
                first_date = w.get("date") or ""
                rows.append([
                    link,
                    f'<span class="score">{score_cell(w, disp)}</span>',
                    holders,
                    fmt_date(first_date),
                    days_between(first_date, NOW),
                    CONSOLES.get(w.get("console"), ""),
                ])
            parts.append(
                f'<section id="c{c["rule"]}"><h3>{e(c["label"])}'
                f' <a class="sub" href="ranking/{c["rule"]}.html">Overall ranking</a></h3>'
                + table(["Stage", "Record", "Player", "Date", "Days", "Console"], rows, f"wrt s{series}")
                + "</section>"
            )
    write(f"{SERIES_SLUG[series]}.html", page(SERIES[series], "\n".join(parts), pre, series))


def board_page(cat, sid):
    pre = "../"
    rule = cat["rule"]
    st = stages.get(sid) or {}
    disp = st
    b = board(rule, sid)
    h = history(rule, sid)
    title = f"{stage_name(sid)} — {cat['label']}"
    parts = [
        f'<p class="crumb"><a href="../{SERIES_SLUG[cat["series"]]}.html#c{rule}">{SERIES[cat["series"]]} · {e(cat["label"])}</a></p>',
        f"<h1>{e(stage_name(sid))}</h1>",
    ]
    facts = []
    if st.get("name_ja") and st.get("name_ja") != st.get("name"):
        facts.append(e(st["name_ja"]))
    if st.get("time"):
        facts.append(f'{st["time"]} s')
    if st.get("treasure"):
        facts.append(f'{st["treasure"]:,} treasure pts')
    if st.get("pikmin"):
        facts.append(f'{st["pikmin"]} starting Pikmin')
    facts.append(f'<a href="{pik5_board_url(rule, sid)}">View on pik5.net</a>')
    parts.append(f'<p class="facts">{" · ".join(facts)}</p>')

    # WR history (newest first, like a history page)
    recs = h.get("records") or []
    # fold ties into the record they matched
    groups: list[tuple[dict, list[dict]]] = []
    for r in recs:
        if r.get("tie") and groups:
            groups[-1][1].append(r)
        else:
            groups.append((r, []))
    rows = []
    for i, (r, ties) in enumerate(groups):
        nxt = groups[i + 1][0] if i + 1 < len(groups) else None
        lasted = days_between(r["date"], nxt["date"] if nxt else NOW)
        tie_cell = ""
        if ties:
            names = ", ".join(f'{player_name(t["user"])} ({fmt_date(t["date"])})' for t in ties)
            tie_cell = f'<span class="tie" title="{e(names)}">+{len(ties)}</span>'
        rows.append([
            fmt_date(r["date"]),
            f'<span class="score">{score_cell(r, disp)}</span>',
            player_link(r["user"], pre),
            tie_cell,
            CONSOLES.get(r.get("console"), ""),
            lasted + ("" if nxt else "+"),
        ])
    rows.reverse()
    note = "" if h.get("backfilled") else (
        '<p class="note">History is recorded from the first sync of this mirror onward; earlier records have not been back-filled yet.</p>'
    )
    parts.append("<h2>Record history</h2>" + note + table(["Date", "Record", "Player", "Tied by", "Console", "Days"], rows, f"hist s{cat['series']}"))

    # full current leaderboard
    rows = []
    for p in b["posts"]:
        rows.append([
            str(p.get("rank") or ""),
            player_link(p["user"], pre),
            f'<span class="score">{score_cell(p, disp)}</span>',
            f'{p["rps"]:,}' if p.get("rps") is not None else "",
            fmt_date(p.get("date")),
            CONSOLES.get(p.get("console"), ""),
            e((p.get("comment") or "")[:80]),
        ])
    parts.append(f"<h2>Current leaderboard <span class='count'>{len(rows)} players</span></h2>"
                 + table(["#", "Player", "Score", "Points", "Date", "Console", "Comment"], rows, f"lb s{cat['series']}"))
    write(f"stage/{rule}-{sid}.html", page(title, "\n".join(parts), pre, cat["series"]))


def ranking_page(rule, name, series, pre="../"):
    t = load(f"totals/{rule}.json")
    if not t:
        return
    rows = [[
        str(r.get("rank") or ""),
        player_link(r["user"], pre),
        f'{r["rps"]:,}' if r.get("rps") is not None else "",
        f'{r["score"]:,}' if r.get("score") is not None else "",
        str(r.get("boards") or ""),
    ] for r in t["rows"]]
    body = (f'<p class="crumb"><a href="../{SERIES_SLUG[series]}.html">{SERIES[series]}</a></p>'
            f"<h1>{e(name)}</h1><p class='facts'>Ranked by pik5 ranking points. "
            f'<a href="{PIK5}/total/{rule}">View on pik5.net</a></p>'
            + table(["#", "Player", "Points", "Total score", "Stages"], rows, f"lb s{series}"))
    write(f"ranking/{rule}.html", page(name, body, pre, series))


def collect_player_data():
    per = {}
    for c in categories:
        for sid in c["stages"]:
            for p in board(c["rule"], sid)["posts"]:
                per.setdefault(p["user"], []).append((c, sid, p))
    return per


def player_page(uid, entries):
    pre = "../"
    entries.sort(key=lambda x: (x[0]["series"], CATS_ORDER[x[0]["rule"]], x[1]))
    wrs = sum(1 for _, _, p in entries if p.get("rank") == 1)
    rows = []
    for c, sid, p in entries:
        disp = stages.get(sid)
        rank = p.get("rank")
        rows.append([
            SERIES[c["series"]],
            e(c["label"]),
            f'<a href="../stage/{c["rule"]}-{sid}.html">{e(stage_name(sid))}</a>',
            f'<span class="score">{score_cell(p, disp)}</span>',
            f'<b class="wr">1</b>' if rank == 1 else str(rank or ""),
            fmt_date(p.get("date")),
        ])
    name = player_name(uid)
    body = (f"<h1>{e(name)}</h1>"
            f'<p class="facts">{len(entries)} records · {wrs} current #1s · '
            f'<a href="{PIK5}/user/{quote(uid, safe="")}">Profile on pik5.net</a></p>'
            + table(["Game", "Category", "Stage", "Score", "Rank", "Date"], rows, "lb"))
    write(f"player/{quote(uid, safe='')}.html", page(name, body, pre, "players"))
    return wrs


def players_index(per, wr_counts):
    rows = []
    for uid in sorted(per, key=lambda u: (-wr_counts.get(u, 0), -len(per[u]), player_name(u).lower())):
        rows.append([player_link(uid, ""), str(wr_counts.get(uid, 0)), str(len(per[uid]))])
    body = "<h1>Players</h1>" + table(["Player", "Current #1s", "Records"], rows, "lb")
    write("players.html", page("Players", body, "", "players"))


def index_page():
    pre = ""
    # recent record changes across all boards
    recent = []
    for c in categories:
        for sid in c["stages"]:
            disp = stages.get(sid)
            for r in history(c["rule"], sid).get("records") or []:
                if r.get("tie"):
                    continue
                recent.append((r.get("date") or "", c, sid, r, disp))
    recent.sort(key=lambda x: x[0], reverse=True)
    rows = [[
        fmt_date(d),
        f'<span class="pill s{c["series"]}">{SERIES[c["series"]]}</span>',
        f'<a href="stage/{c["rule"]}-{sid}.html">{e(stage_name(sid))}</a><span class="cat"> · {e(c["label"])}</span>',
        f'<span class="score">{score_cell(r, disp)}</span>' + (' <span class="tie">tie</span>' if r.get("tie") else ""),
        player_link(r["user"], pre),
    ] for d, c, sid, r, disp in recent[:60]]

    cards = "".join(
        f'<a class="card s{s}" href="{SERIES_SLUG[s]}.html"><b>{SERIES[s]}</b>'
        f'<span>{sum(len(c["stages"]) for c in categories if c["series"] == s)} boards</span></a>'
        for s in SERIES
    )
    rankings = " · ".join(
        f'<a href="ranking/{tid}.html">{SERIES[s]}</a>' for s, tid in ((1, 10), (2, 20), (3, 30), (4, 40))
        if (DATA / "totals" / f"{tid}.json").exists()
    )
    body = (
        "<h1>Pikmin Score Records</h1>"
        "<p class='lead'>Current records and record history for every Pikmin challenge-mode board on pik5.net.</p>"
        f'<div class="cards">{cards}</div>'
        f"<p class='toc'>Overall rankings: {rankings}</p>"
        "<h2>Recent records</h2>"
        + table(["Date", "Game", "Stage", "Record", "Player"], rows, "recent")
    )
    write("index.html", page("Home", body, pre))


CATS_ORDER = {c["rule"]: i for i, c in enumerate(categories)}


def main():
    if not categories:
        raise SystemExit("no data — run sync/pik5_sync.py first")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copy(SRC / "style.css", DIST / "style.css")
    for s in SERIES:
        series_page(s)
    for c in categories:
        for sid in c["stages"]:
            board_page(c, sid)
        ranking_page(c["rule"], c["name"] or c["label"], c["series"])
    for s, tid in ((1, 10), (2, 20), (3, 30), (4, 40)):
        ranking_page(tid, f"{SERIES[s]} overall ranking", s)
    per = collect_player_data()
    wr_counts = {uid: player_page(uid, entries) for uid, entries in per.items()}
    players_index(per, wr_counts)
    index_page()
    n = sum(1 for _ in DIST.rglob("*.html"))
    print(f"built {n} pages into {DIST}")


if __name__ == "__main__":
    main()
