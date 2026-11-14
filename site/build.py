"""Render the mirrored pik5 data in data/ as a static, bilingual site in dist/.

    python site/build.py

Output: dist/index.html (language redirect), dist/en/..., dist/ja/...
"""

from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from i18n import CAT_LABELS, COUNTRIES, GAMES, STR
from icons import EGG, console_icon, video_icon

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
SRC = Path(__file__).resolve().parent
PIK5 = "https://pik5.net"
NOW = datetime.now(timezone.utc)
LANGS = ("en", "ja")
FLAG_CDN = "https://cdn.jsdelivr.net/npm/flag-icons@7.2.3/flags/4x3/{}.svg"
SLUG = {1: "pikmin1", 2: "pikmin2", 3: "pikmin3", 4: "pikmin4"}
TOTAL_OF = {1: 10, 2: 20, 3: 30, 4: 40}

e = html.escape
JA_RE = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")

# Score -> time formulas for categories whose score has a time component.
# Each takes (score, stage_info) and returns (time_used_s, time_left_s) or None.
# Left empty until the scoring rules are confirmed; see README.
TIME_FORMULAS: dict = {}


def load(name, default=None):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


meta = load("meta.json", {})
raw_categories = load("categories.json", [])
stages = {int(k): v for k, v in load("stages.json", {}).items()}
users = load("users.json", {})
profiles = load("players.json", {})
overrides = {k: v for k, v in json.loads((SRC / "players_overrides.json").read_text(encoding="utf-8")).items()
             if not k.startswith("_")}


@lru_cache(maxsize=None)
def board(key):
    return load(f"boards/{key}.json", {"posts": [], "lower_is_better": False})


@lru_cache(maxsize=None)
def history(key):
    return load(f"history/{key}.json", {"records": []})


@lru_cache(maxsize=None)
def archive(key):
    return load(f"archive/{key}.json", {"posts": []})


# ---------------------------------------------------------------- categories
# Display categories. Pikmin 2's egg / no-egg boards are one challenge mode on
# pik5's side split by stage, so they're merged here with an egg marker.

def build_categories():
    out = []
    by_rule = {c["rule"]: c for c in raw_categories}
    for c in raw_categories:
        r = c["rule"]
        if r == 22 and 21 in by_rule:
            continue
        if r == 21 and 22 in by_rule:
            boards = [(21, s) for s in by_rule[21]["stages"]] + [(22, s) for s in by_rule[22]["stages"]]
            boards.sort(key=lambda b: b[1])
            out.append({"id": "p2", "series": 2, "kind": "main", "rules": [21, 22],
                        "boards": boards, "total": 20, "egg_rule": 21})
            continue
        out.append({"id": str(r), "series": c["series"], "kind": c["kind"], "rules": [r],
                    "boards": [(r, s) for s in c["stages"]], "total": r})
    return out


CATS = build_categories()


def bkey(rule, sid):
    return f"{rule}-{sid}"


# ---------------------------------------------------------------- text helpers

class T:
    """Per-language helpers."""

    def __init__(self, lang):
        self.lang = lang

    def s(self, key, **kw):
        txt = STR[key][self.lang]
        return txt.format(**kw) if kw else txt

    def game(self, series):
        return GAMES[series][self.lang]

    def cat(self, c):
        return CAT_LABELS[c["id"]][self.lang]

    def stage(self, sid):
        st = stages.get(sid) or {}
        if self.lang == "ja":
            return st.get("name_ja") or st.get("name") or f"#{sid}"
        return st.get("name") or st.get("name_ja") or f"#{sid}"

    def date(self, s):
        d = parse_date(s)
        return d.strftime("%Y-%m-%d") if d else ""


def parse_date(s):
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def days_between(a, b):
    da, db = parse_date(a), parse_date(b)
    if not da or not db:
        return ""
    return str(max(0, (db - da).days))


# ---------------------------------------------------------------- players

def english_name(uid):
    return overrides.get(uid, {}).get("en") or profiles.get(uid, {}).get("src_name") or None


def country(uid):
    """(code, inferred?)"""
    o = overrides.get(uid, {}).get("country")
    if o:
        return o.lower(), False
    c = profiles.get(uid, {}).get("country")
    if c:
        return c, False
    if JA_RE.search(users.get(uid, "")):
        return "jp", True
    return None, False


def flag(uid, t: T):
    code, inferred = country(uid)
    if not code:
        return ""
    name = COUNTRIES.get(code, {}).get(t.lang, code.upper())
    if inferred:
        name = t.s("inferred", name=name)
    return f'<img class="flag" src="{FLAG_CDN.format(code)}" alt="{code.upper()}" title="{e(name)}" loading="lazy">'


def player(uid, t: T, pre):
    if not uid:
        return "?"
    name = users.get(uid) or uid
    label = e(name)
    if t.lang == "en" and JA_RE.search(name):
        alt = english_name(uid)
        if alt:
            label += f' <span class="romaji">({e(alt)})</span>'
    return f'<a href="{pre}player/{quote(uid, safe="")}.html">{label}</a>'


# ---------------------------------------------------------------- scores

def mmss(sec):
    sec = int(sec)
    m, s = divmod(abs(sec), 60)
    h, m = divmod(m, 60)
    out = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
    return ("-" if sec < 0 else "") + out


def score_views(score, rule, sid):
    """(pik5-style score text, time used text|None, time left text|None)."""
    st = stages.get(sid) or {}
    disp = st.get("display")
    limit = st.get("time") or 0
    if disp == "speedrun":
        return mmss(score), mmss(score), (mmss(limit - score) if limit else None)
    if disp == "time":
        if limit:
            return mmss(limit - score), mmss(limit - score), mmss(score)
        return mmss(score), None, mmss(score)
    f = TIME_FORMULAS.get(rule)
    if f:
        r = f(score, st)
        if r:
            return f"{score:,}", mmss(r[0]), mmss(r[1])
    return f"{score:,}", None, None


def score_cell(p, rule, sid, t: T):
    if p.get("score") is None:
        return ""
    s, used, left = score_views(p["score"], rule, sid)
    na = e(t.s("no_time"))

    def span(cls, val):
        if val is None:
            return f'<span class="v {cls} na" title="{na}">{s}</span>'
        return f'<span class="v {cls}">{val}</span>'

    return f'<span class="score">{span("v-s", s)}{span("v-u", used)}{span("v-l", left)}</span>'


# ---------------------------------------------------------------- video

def norm_video(v):
    v = (v or "").strip()
    if not v:
        return ""
    if not v.startswith("http"):
        v = "https://www.youtube.com/watch?v=" + v
    return v


def youtube_id(url):
    u = urlparse(url)
    host = u.netloc.lower()
    if host.endswith("youtu.be"):
        return u.path.strip("/").split("/")[0] or None
    if "youtube" in host:
        if u.path == "/watch":
            return (parse_qs(u.query).get("v") or [None])[0]
        m = re.match(r"/(shorts|live|embed)/([^/?]+)", u.path)
        if m:
            return m.group(2)
    return None


def video_cell(p, t: T):
    v = norm_video(p.get("video"))
    if not v:
        return ""
    icon, kind = video_icon(v)
    title = t.s("watch_on", site=kind)
    return f'<a class="ico" href="{e(v)}" target="_blank" rel="noopener" title="{e(title)}">{icon}</a>'


def best_with_video(key, low):
    posts = [p for p in board(key)["posts"] if norm_video(p.get("video"))]
    if not posts:
        return None
    return sorted(posts, key=lambda p: ((p["score"] if low else -p["score"]), p.get("date") or ""))[0]


def embed(p, t: T):
    v = norm_video(p.get("video"))
    if not v:
        return ""
    yid = youtube_id(v)
    if not yid:
        return ""
    thumb = f"https://i.ytimg.com/vi/{quote(yid)}/hqdefault.jpg"
    return (f'<div class="yt" data-id="{e(yid)}" style="background-image:url({thumb})">'
            f'<button type="button" aria-label="{e(t.s("play"))}"></button></div>')


def console_cell(code, t: T):
    return console_icon(code, t.lang)


# ---------------------------------------------------------------- layout

def page(t: T, rel, title, body, *, series=None, current_key=None, body_extra=""):
    depth = rel.count("/")
    pre = "../" * depth
    games = " | ".join(f'<a href="{pre}{SLUG[s]}.html"{" class=on" if series == s else ""}>{e(t.game(s))}</a>'
                       for s in GAMES)
    topnav = (f'[ <a href="{pre}index.html">{e(t.s("home"))}</a> | {games} | '
              f'<a href="{pre}players.html">{e(t.s("players"))}</a> ]')
    langnav = (f'[ <a data-lang="en" href="{pre}../en/{rel}"{" class=on" if t.lang == "en" else ""}>English</a> | '
               f'<a data-lang="ja" href="{pre}../ja/{rel}"{" class=on" if t.lang == "ja" else ""}>日本語</a> ]')
    modenav = (f'[ <a href="#" data-mode="s">{e(t.s("mode_s"))}</a> | '
               f'<a href="#" data-mode="u">{e(t.s("mode_u"))}</a> | '
               f'<a href="#" data-mode="l">{e(t.s("mode_l"))}</a> ]')

    side = [f'<div class="navbox"><a class="head" href="{pre}index.html">{e(t.s("games"))}</a>']
    for s in GAMES:
        on = ' class="on"' if series == s else ""
        side.append(f'<a{on} href="{pre}{SLUG[s]}.html">{e(t.game(s))}</a>')
    side.append(f'<a href="{pre}players.html">{e(t.s("players"))}</a></div>')
    if series:
        for c in [c for c in CATS if c["series"] == series]:
            side.append(f'<div class="navbox"><a class="head" href="{pre}{SLUG[series]}.html#c{c["id"]}">{e(t.cat(c))}</a>')
            for r, sid in c["boards"]:
                k = bkey(r, sid)
                on = ' class="on"' if k == current_key else ""
                egg = EGG if c.get("egg_rule") == r else ""
                side.append(f'<a{on} href="{pre}history/{k}.html">{e(t.stage(sid))}{egg}</a>')
            side.append("</div>")

    synced = parse_date(meta.get("synced_at"))
    synced_txt = synced.strftime("%Y-%m-%d %H:%M UTC") if synced else "?"
    return f"""<!doctype html>
<html lang="{t.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} - {e(t.s("site"))}</title>
<link rel="stylesheet" href="{pre}../style.css">
<script>try{{document.documentElement.dataset.mode=localStorage.getItem("mode")||"s"}}catch(_){{}}</script>
</head>
<body>
<div id="outer">
<div id="header">
  <div class="logo"><a href="{pre}index.html">{e(t.s("site"))}</a></div>
  <div class="bars">
    <div>{topnav}</div>
    <div>{langnav} <span class="modes">{e(t.s("show"))}: {modenav}</span></div>
  </div>
</div>
<button id="menubtn" type="button" aria-expanded="false">&#9776; {e(t.s("menu"))}</button>
<div id="cols">
<nav id="nav">{''.join(side)}</nav>
<div id="main">
{body}
<div id="footer">{t.s("footer", pik5=f'<a href="{PIK5}/{t.lang}/">pik5.net</a>', synced=synced_txt)}</div>
</div>
</div>
</div>
{body_extra}
<script src="{pre}../site.js"></script>
</body>
</html>
"""


def table(headers, rows, cls="wr"):
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join(
        (f'<tr class="{r[0]}">' if isinstance(r, tuple) else "<tr>")
        + "".join(f"<td>{c}</td>" for c in (r[1] if isinstance(r, tuple) else r)) + "</tr>"
        for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'


def write(lang, rel, content):
    p = DIST / lang / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def pik5_url(key, t: T):
    r, s = key.split("-")
    return f"{PIK5}/{t.lang}/stage/{s}" if r == "48" else f"{PIK5}/{t.lang}/stage/{s}/0/{r}"


def board_tabs(t: T, key, active, pre):
    def a(k, href, label):
        return f'<a href="{href}"{" class=on" if active == k else ""}>{e(label)}</a>'
    return (f'<p class="tabs">[ {a("hist", f"{pre}history/{key}.html", t.s("wr_history"))} | '
            f'{a("lb", f"{pre}board/{key}.html", t.s("leaderboard"))} | '
            f'<a href="{pik5_url(key, t)}" target="_blank" rel="noopener">{e(t.s("on_pik5"))}</a> ]</p>')


def stage_heading(t: T, c, rule, sid):
    st = stages.get(sid) or {}
    facts = [f'<a href="../{SLUG[c["series"]]}.html#c{c["id"]}">{e(t.game(c["series"]))} · {e(t.cat(c))}</a>']
    if t.lang == "en" and st.get("name_ja") and st.get("name_ja") != st.get("name"):
        facts.append(e(st["name_ja"]))
    if st.get("time"):
        facts.append(e(t.s("time_limit", t=mmss(st["time"]))))
    if st.get("pikmin"):
        facts.append(e(t.s("start_pikmin", n=st["pikmin"])))
    egg = ""
    if c.get("egg_rule") == rule:
        egg = f' <span class="eggnote">{EGG} {e(t.s("egg_stage"))}</span>'
    return f'<h1>{e(t.stage(sid))}{egg}</h1><p class="facts">{" · ".join(facts)}</p>'


# ---------------------------------------------------------------- pages

def current_wrs(key):
    wrs = [p for p in board(key)["posts"] if p.get("rank") == 1]
    return sorted(wrs, key=lambda p: p.get("date") or "")


def game_page(t: T, series):
    pre = ""
    cats = [c for c in CATS if c["series"] == series]
    parts = [f"<h1>{e(t.s('game_title', game=t.game(series)))}</h1>"]
    parts.append('<p class="tabs">[ ' + " | ".join(f'<a href="#c{c["id"]}">{e(t.cat(c))}</a>' for c in cats)
                 + f' | <a href="#overall">{e(t.s("overall"))}</a> ]</p>')
    for kind in ("main", "special"):
        group = [c for c in cats if c["kind"] == kind]
        if not group:
            continue
        parts.append(f"<h2>{e(t.s('cur_wrs' if kind == 'main' else 'cur_wrs_special'))}</h2>")
        for c in group:
            rows = []
            for r, sid in c["boards"]:
                k = bkey(r, sid)
                b = board(k)
                wrs = current_wrs(k)
                egg = EGG if c.get("egg_rule") == r else ""
                link = f'<a href="history/{k}.html">{e(t.stage(sid))}</a>{egg}'
                if not wrs:
                    rows.append([link, "—", "", "", "", "", "", ""])
                    continue
                w = wrs[0]
                if len(wrs) <= 2:
                    who = "<br>".join(player(p["user"], t, pre) for p in wrs)
                    nat = "<br>".join(flag(p["user"], t) for p in wrs)
                else:
                    others = ", ".join(users.get(p["user"], p["user"]) for p in wrs[1:])
                    who = (f'{player(w["user"], t, pre)} <a class="tie" title="{e(others)}" href="board/{k}.html">'
                           f'{e(t.s("plus_tied", n=len(wrs) - 1))}</a>')
                    nat = flag(w["user"], t)
                vid = next((p for p in wrs if norm_video(p.get("video"))), None)
                rows.append([link, score_cell(w, r, sid, t), who, nat, t.date(w.get("date")),
                             days_between(w.get("date"), NOW), console_cell(w.get("console"), t),
                             video_cell(vid, t) if vid else ""])
                if not vid:
                    bv = best_with_video(k, b.get("lower_is_better"))
                    if bv:
                        rows.append(("proof", [
                            f'<span class="small">↳ {e(t.s("best_video"))}</span>', score_cell(bv, r, sid, t),
                            player(bv["user"], t, pre), flag(bv["user"], t), t.date(bv.get("date")), "",
                            console_cell(bv.get("console"), t), video_cell(bv, t)]))
            ranking = ("" if c["id"] == "p2" else
                       f' <span class="small">[ <a href="ranking/{c["total"]}.html">{e(t.s("cat_ranking"))}</a> ]</span>')
            parts.append(
                f'<h3 id="c{c["id"]}">{e(t.cat(c))}{ranking}</h3>'
                + table([t.s("stage"), t.s("score"), t.s("player"), t.s("nation"), t.s("date"),
                         t.s("days"), t.s("console"), t.s("video")], rows))
    parts.append(f'<h2 id="overall">{e(t.s("overall_title", game=t.game(series)))}</h2>')
    parts.append(ranking_table(t, TOTAL_OF[series], pre))
    write(t.lang, f"{SLUG[series]}.html", page(t, f"{SLUG[series]}.html", t.game(series), "\n".join(parts),
                                               series=series))


def ranking_table(t: T, total_id, pre, limit=None):
    tot = load(f"totals/{total_id}.json")
    if not tot:
        return ""
    rows = [[str(r.get("rank") or ""), player(r["user"], t, pre), flag(r["user"], t),
             f'<b>{r["score"]:,}</b>' if r.get("score") is not None else "",
             f'{r["rps"]:,}' if r.get("rps") is not None else "", str(r.get("boards") or "")]
            for r in tot["rows"][:limit]]
    return table(["#", t.s("player"), t.s("nation"), t.s("total_score"), t.s("points"), t.s("stages")], rows)


def ranking_page(t: T, total_id, title, series):
    rel = f"ranking/{total_id}.html"
    body = (f"<h1>{e(title)}</h1><p class='facts'>{e(t.s('ranked_by_points'))} "
            f'[ <a href="{PIK5}/{t.lang}/total/{total_id}" target="_blank" rel="noopener">{e(t.s("on_pik5"))}</a> ]</p>'
            + ranking_table(t, total_id, "../"))
    write(t.lang, rel, page(t, rel, title, body, series=series))


def history_page(t: T, c, rule, sid):
    pre = "../"
    k = bkey(rule, sid)
    rel = f"history/{k}.html"
    h = history(k)
    b = board(k)
    low = b.get("lower_is_better")
    parts = [stage_heading(t, c, rule, sid), board_tabs(t, k, "hist", pre)]

    wrs = current_wrs(k)
    if wrs:
        w = wrs[0]
        vid = next((p for p in wrs if norm_video(p.get("video"))), None)
        rows = [[t.date(p.get("date")), score_cell(p, rule, sid, t), player(p["user"], t, pre), flag(p["user"], t),
                 console_cell(p.get("console"), t), video_cell(p, t), days_between(p.get("date"), NOW)]
                for p in wrs[:5]]
        more = f'<p class="small">{e(t.s("and_more_tied", n=len(wrs) - 5))}</p>' if len(wrs) > 5 else ""
        parts.append(f"<h2>{e(t.s('current_wr'))}</h2>"
                     + table([t.s("date"), t.s("score"), t.s("player"), t.s("nation"), t.s("console"), t.s("video"),
                              t.s("days")], rows) + more)
        shown = vid
        if not vid:
            bv = best_with_video(k, low)
            if bv:
                parts.append(f'<p class="note">{e(t.s("no_wr_video"))}</p>'
                             + table([t.s("date"), t.s("score"), t.s("player"), t.s("nation"), t.s("console"),
                                      t.s("video")],
                                     [[t.date(bv.get("date")), score_cell(bv, rule, sid, t), player(bv["user"], t, pre),
                                       flag(bv["user"], t), console_cell(bv.get("console"), t), video_cell(bv, t)]]))
                shown = bv
        if shown:
            parts.append(embed(shown, t))

    recs = h.get("records") or []
    groups = []
    for r in recs:
        if r.get("tie") and groups:
            groups[-1][1].append(r)
        else:
            groups.append((r, []))
    rows = []
    for i, (r, ties) in enumerate(groups):
        nxt = groups[i + 1][0] if i + 1 < len(groups) else None
        lasted = days_between(r["date"], nxt["date"] if nxt else NOW) + ("" if nxt else "+")
        tie = ""
        if ties:
            names = ", ".join(f'{users.get(x["user"], x["user"])} ({t.date(x["date"])})' for x in ties)
            tie = f'<span class="tie" title="{e(names)}">+{len(ties)}</span>'
        rows.append([t.date(r["date"]), score_cell(r, rule, sid, t), player(r["user"], t, pre), flag(r["user"], t),
                     tie, console_cell(r.get("console"), t), video_cell(r, t), lasted])
    rows.reverse()
    note = "" if h.get("backfilled") else f'<p class="note">{e(t.s("not_backfilled"))}</p>'
    parts.append(f"<h2>{e(t.s('history'))}</h2>" + note
                 + table([t.s("date"), t.s("score"), t.s("player"), t.s("nation"), t.s("tied_by"), t.s("console"),
                          t.s("video"), t.s("days")], rows))
    write(t.lang, rel, page(t, rel, f"{t.stage(sid)} - {t.cat(c)}", "\n".join(parts), series=c["series"],
                            current_key=k))


def board_page(t: T, c, rule, sid):
    pre = "../"
    k = bkey(rule, sid)
    rel = f"board/{k}.html"
    b = board(k)
    low = bool(b.get("lower_is_better"))
    head = ["#", t.s("player"), t.s("nation"), t.s("score"), t.s("points"), t.s("date"), t.s("console"),
            t.s("video"), t.s("comment")]
    rows = [[str(p.get("rank") or ""), player(p["user"], t, pre), flag(p["user"], t), score_cell(p, rule, sid, t),
             f'{p["rps"]:,}' if p.get("rps") is not None else "", t.date(p.get("date")),
             console_cell(p.get("console"), t), video_cell(p, t), e((p.get("comment") or "")[:80])]
            for p in b["posts"]]

    # snapshot data: every archived submission, with pre-rendered cells
    arc = archive(k)["posts"]
    snap = {
        "low": low,
        "rows": [{"u": a["user"], "s": a["score"], "d": t.date(a.get("date")),
                  "c": [player(a["user"], t, pre), flag(a["user"], t), score_cell(a, rule, sid, t), "",
                        t.date(a.get("date")), console_cell(a.get("console"), t), video_cell(a, t),
                        e((a.get("comment") or "")[:80])]}
                 for a in arc if a.get("score") is not None],
    }
    earliest = min((r["d"] for r in snap["rows"] if r["d"]), default="")
    picker = (f'<form class="snap" onsubmit="return false">{e(t.s("as_of"))} '
              f'<input type="date" id="asof" min="{earliest}" max="{NOW:%Y-%m-%d}"> '
              f'<button type="button" id="asof-reset">{e(t.s("today"))}</button> '
              f'<span class="small" id="asof-note"></span></form>'
              f'<p class="note">{e(t.s("snapshot_note", n=len(snap["rows"])))}</p>')
    data = json.dumps(snap, ensure_ascii=False).replace("</", "<\\/")
    texts = json.dumps({"players": t.s("n_players", n="{n}"), "asof": t.s("snapshot_shown")}, ensure_ascii=False)
    body = (stage_heading(t, c, rule, sid) + board_tabs(t, k, "lb", pre)
            + f"<h2>{e(t.s('leaderboard'))} <span class='small' id='lb-count'>{e(t.s('n_players', n=len(rows)))}</span></h2>"
            + picker + table(head, rows, "wr lb"))
    extra = (f'<script type="application/json" id="snapdata">{data}</script>'
             f'<script>window.SNAP_TEXT={texts}</script>')
    write(t.lang, rel, page(t, rel, f"{t.stage(sid)} - {t.cat(c)}", body, series=c["series"], current_key=k,
                            body_extra=extra))


def collect_player_entries():
    per = {}
    for c in CATS:
        for r, sid in c["boards"]:
            for p in board(bkey(r, sid))["posts"]:
                per.setdefault(p["user"], []).append((c, r, sid, p))
    return per


def player_page(t: T, uid, entries):
    rel = f"player/{quote(uid, safe='')}.html"
    order = {c["id"]: i for i, c in enumerate(CATS)}
    entries = sorted(entries, key=lambda x: (x[0]["series"], order[x[0]["id"]], x[2]))
    wrs = sum(1 for *_, p in entries if p.get("rank") == 1)
    rows = []
    for c, r, sid, p in entries:
        rank = p.get("rank")
        rows.append([e(t.game(c["series"])), e(t.cat(c)),
                     f'<a href="../history/{bkey(r, sid)}.html">{e(t.stage(sid))}</a>',
                     score_cell(p, r, sid, t), '<b class="gold">1</b>' if rank == 1 else str(rank or ""),
                     t.date(p.get("date")), console_cell(p.get("console"), t), video_cell(p, t)])
    name = users.get(uid) or uid
    alt = english_name(uid) if (t.lang == "en" and JA_RE.search(name)) else None
    title = e(name) + (f' <span class="romaji">({e(alt)})</span>' if alt else "")
    src = profiles.get(uid, {}).get("src")
    links = [f'<a href="{PIK5}/{t.lang}/user/{quote(uid, safe="")}" target="_blank" rel="noopener">pik5.net</a>']
    if src:
        links.append(f'<a href="https://www.speedrun.com/users/{quote(src)}" target="_blank" rel="noopener">speedrun.com</a>')
    body = (f"<h1>{flag(uid, t)} {title}</h1>"
            f'<p class="facts">{e(t.s("player_facts", n=len(entries), w=wrs))} [ {" | ".join(links)} ]</p>'
            + table([t.s("game"), t.s("category"), t.s("stage"), t.s("score"), t.s("rank"), t.s("date"),
                     t.s("console"), t.s("video")], rows))
    write(t.lang, rel, page(t, rel, name, body))
    return wrs


def players_index(t: T, per, wr_counts):
    rows = [[player(uid, t, ""), flag(uid, t), str(wr_counts.get(uid, 0)), str(len(per[uid]))]
            for uid in sorted(per, key=lambda u: (-wr_counts.get(u, 0), -len(per[u]), (users.get(u) or u).lower()))]
    body = f"<h1>{e(t.s('players'))}</h1>" + table([t.s("player"), t.s("nation"), t.s("cur_firsts"), t.s("records")], rows)
    write(t.lang, "players.html", page(t, "players.html", t.s("players"), body))


def index_page(t: T):
    pre = ""
    recent = []
    for c in CATS:
        for r, sid in c["boards"]:
            for rec in history(bkey(r, sid)).get("records") or []:
                if not rec.get("tie"):
                    recent.append((rec.get("date") or "", c, r, sid, rec))
    recent.sort(key=lambda x: x[0], reverse=True)
    rows = [[t.date(d), e(t.game(c["series"])),
             f'<a href="history/{bkey(r, sid)}.html">{e(t.stage(sid))}</a> <span class="small">({e(t.cat(c))})</span>',
             score_cell(rec, r, sid, t), player(rec["user"], t, pre), flag(rec["user"], t), video_cell(rec, t)]
            for d, c, r, sid, rec in recent[:50]]
    games = "".join(
        f'<li><a href="{SLUG[s]}.html">{e(t.game(s))}</a> <span class="small">'
        f'({e(t.s("n_boards", n=sum(len(c["boards"]) for c in CATS if c["series"] == s)))})</span></li>'
        for s in GAMES)
    pik5_link = f'<a href="{PIK5}/{t.lang}/">pik5.net</a>'
    body = (f"<h1>{e(t.s('site'))}</h1><p>{t.s('intro', pik5=pik5_link)}</p>"
            f"<ul class='games'>{games}</ul>"
            f"<h2>{e(t.s('recent'))}</h2>"
            + table([t.s("date"), t.s("game"), t.s("stage"), t.s("score"), t.s("player"), t.s("nation"), t.s("video")],
                    rows))
    write(t.lang, "index.html", page(t, "index.html", t.s("home"), body))


ROOT_INDEX = """<!doctype html>
<html><head><meta charset="utf-8"><title>Pikmin Score Records</title>
<script>
(function(){var l;try{l=localStorage.getItem("lang")}catch(_){}
if(l!=="en"&&l!=="ja"){var ls=navigator.languages||[navigator.language||"en"];
l=ls.some(function(x){return /^ja\\b/i.test(x)})?"ja":"en"}
location.replace(l+"/index.html")})();
</script></head>
<body><p><a href="en/index.html">English</a> · <a href="ja/index.html">日本語</a></p></body></html>
"""


def main():
    if not raw_categories:
        raise SystemExit("no data — run sync/pik5_sync.py first")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copy(SRC / "style.css", DIST / "style.css")
    shutil.copy(SRC / "site.js", DIST / "site.js")
    (DIST / "index.html").write_text(ROOT_INDEX, encoding="utf-8")
    per = collect_player_entries()
    for lang in LANGS:
        t = T(lang)
        for s in GAMES:
            game_page(t, s)
        for c in CATS:
            for r, sid in c["boards"]:
                history_page(t, c, r, sid)
                board_page(t, c, r, sid)
            if c["id"] != "p2":
                ranking_page(t, c["total"], t.s("cat_ranking_title", cat=t.cat(c), game=t.game(c["series"])),
                             c["series"])
        for s, tid in TOTAL_OF.items():
            ranking_page(t, tid, t.s("overall_title", game=t.game(s)), s)
        wr_counts = {uid: player_page(t, uid, ent) for uid, ent in per.items()}
        players_index(t, per, wr_counts)
        index_page(t)
    n = sum(1 for _ in DIST.rglob("*.html"))
    print(f"built {n} pages into {DIST}")


if __name__ == "__main__":
    main()
