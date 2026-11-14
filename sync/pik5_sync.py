"""Mirror leaderboard data from pik5.net into normalized JSON under data/.

pik5.net is a Next.js app: every page's data is served as JSON at
/_next/data/<buildId>/en/<path>.json. We read the current buildId from the
homepage, then walk category totals -> (category, stage) boards.

Usage:
    python sync/pik5_sync.py                 # regular sync (~400 requests)
    python sync/pik5_sync.py backfill [RULE ...]
        # reconstruct WR history from pik5's yearly snapshots (~20 requests
        # per board; restrict to some categories by listing rule ids)

Be polite: requests are serialized with a delay. Only pages allowed by
pik5.net/robots.txt are fetched.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://pik5.net"
USER_AGENT = "pik5-mirror/0.1 (unofficial mirror; polite sync)"
DELAY = 1.5  # seconds between requests
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Categories ("rules") as pik5 organizes them. Rule ids are stable on the site.
# series -> list of (rule, short english label, kind) ; kind: main | special
CATEGORIES = [
    (1, 10, "Challenge Mode", "main"),
    (1, 11, "All-Treasure Time Attack", "special"),
    (2, 21, "Challenge Mode (Eggs)", "main"),
    (2, 22, "Challenge Mode (No Eggs)", "main"),
    (2, 23, "No Mitites", "special"),
    (2, 24, "No Spray", "special"),
    (2, 25, "Story Caves", "special"),
    (2, 26, "2-Player Challenge", "special"),
    (2, 27, "Real Hardware Open Class", "special"),
    (2, 28, "TAS", "special"),
    (2, 29, "Solo Battle", "special"),
    (3, 31, "Collect Treasure!", "main"),
    (3, 32, "Battle Enemies!", "main"),
    (3, 33, "Defeat Bosses!", "main"),
    (3, 36, "Side Stories", "main"),
    (3, 34, "2-Player Missions", "special"),
    (3, 35, "Solo Bingo", "special"),
    (4, 41, "Dandori Challenge", "main"),
    (4, 42, "Dandori Battle", "main"),
    (4, 43, "Trial of the Sage Leaf", "main"),
    (4, 48, "Dandori Exam for Everyone", "main"),
    (4, 44, "Ultra-Spicy Challenge", "special"),
    (4, 45, "Ultra-Spicy Battle", "special"),
    (4, 46, "Ultra-Spicy Sage Leaf", "special"),
    (4, 47, "Night Expedition RTA", "special"),
]
SERIES_TOTALS = {1: 10, 2: 20, 3: 30, 4: 40}
FIRST_YEAR = 2006

_last_request = 0.0


def fetch(url: str, *, as_json: bool, tries: int = 4):
    global _last_request
    for attempt in range(tries):
        wait = DELAY - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8")
            return json.loads(body) if as_json else body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            err = e
        backoff = 5 * 2**attempt
        print(f"  ! {url}: {err}; retrying in {backoff}s", file=sys.stderr)
        time.sleep(backoff)
    raise RuntimeError(f"giving up on {url}")


class Client:
    def __init__(self):
        html = fetch(f"{BASE}/en", as_json=False)
        m = re.search(r'"buildId":"([^"]+)"', html)
        if not m:
            raise RuntimeError("could not find Next.js buildId on homepage")
        self.build_id = m.group(1)

    def page(self, path: str) -> dict | None:
        url = f"{BASE}/_next/data/{self.build_id}/en/{path}.json"
        d = fetch(url, as_json=True)
        if d is None:
            return None
        if "pageProps" not in d:
            return None
        return d["pageProps"]


# ---------------------------------------------------------------- helpers

def write_json(path: Path, obj) -> bool:
    """Write only if content changed. Returns True if the file changed."""
    text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def read_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def stage_info(info: dict) -> dict:
    return {
        "id": int(info["stage_id"]),
        "code": info.get("stage_code"),
        "name": info.get("eng_stage_name") or info.get("stage_name"),
        "name_ja": info.get("stage_name"),
        "sub": info.get("stage_sub"),
        "series": info.get("series"),
        "display": info.get("display"),
        "time": info.get("time"),
        "treasure": info.get("treasure"),
        "pikmin": info.get("pikmin"),
    }


def norm_post(p: dict) -> dict:
    return {
        "id": p.get("post_id"),
        "uid": p.get("unique_id"),
        "user": p.get("user_id"),
        "score": p.get("score"),
        "rank": p.get("post_rank"),
        "rps": p.get("rps"),
        "console": p.get("console"),
        "difficulty": p.get("difficulty"),
        "date": p.get("created_at"),
        "comment": p.get("post_comment") or "",
        "video": p.get("video_url") or "",
        "img": p.get("img_url") or "",
        "team": p.get("team") or 0,
        "certified": bool(p.get("is_certified")),
        "trial": bool(p.get("is_trial")),
    }


def board_path(rule: int, stage: int) -> str:
    # Dandori Exam (48) stages only live at /stage/<id>
    return f"stage/{stage}" if rule == 48 else f"stage/{stage}/0/{rule}"


def lower_is_better(posts: list[dict]) -> bool:
    ranked = [p for p in posts if p["rank"] is not None]
    if len(ranked) < 2:
        return False
    first = min(ranked, key=lambda p: p["rank"])
    last = max(ranked, key=lambda p: p["rank"])
    return first["score"] < last["score"]


def merge_history(hist: list[dict], candidates: list[dict], low: bool) -> list[dict]:
    """Merge candidate posts into a WR progression: chronological, each entry
    better than or tying the standing record (ties by new players are kept)."""
    pool = {(h["user"], h["score"]): h for h in hist}
    for c in candidates:
        key = (c["user"], c["score"])
        if key not in pool or (c["date"] or "") < (pool[key]["date"] or ""):
            pool[key] = c
    out: list[dict] = []
    best = None
    holders: set[str] = set()
    for p in sorted(pool.values(), key=lambda p: (p["date"] or "", p["score"] * (1 if low else -1))):
        s = p["score"]
        if s is None:
            continue
        if best is None or (s < best if low else s > best):
            best, holders = s, {p["user"]}
            out.append({**p, "tie": False})
        elif s == best and p["user"] not in holders:
            holders.add(p["user"])
            out.append({**p, "tie": True})
    return out


def wr_entry(p: dict) -> dict:
    keep = ("id", "uid", "user", "score", "date", "video", "img", "console", "comment")
    return {k: p.get(k) for k in keep}


# ---------------------------------------------------------------- sync

def sync():
    started = datetime.now(timezone.utc)
    c = Client()
    print(f"buildId {c.build_id}")
    users: dict[str, str] = {}
    changed = 0
    categories_out = []
    stages_out: dict[int, dict] = read_json(DATA / "stages.json", {})
    stages_out = {int(k): v for k, v in stages_out.items()}

    # series overall rankings
    for series, total_id in SERIES_TOTALS.items():
        d = c.page(f"total/{total_id}")
        if not d:
            print(f"  ! no data for series total {total_id}")
            continue
        users.update({u["userId"]: u["name"] for u in d.get("users", [])})
        changed += write_json(DATA / "totals" / f"{total_id}.json", total_payload(d, total_id))
        print(f"series {series} total: {len(d.get('posts') or [])} players")

    for series, rule, label, kind in CATEGORIES:
        d = c.page(f"total/{rule}")
        if not d or not d.get("info"):
            print(f"  ! no data for category {rule}")
            continue
        stage_ids = [int(s) for s in d.get("stages") or []]
        changed += write_json(DATA / "totals" / f"{rule}.json", total_payload(d, rule))
        categories_out.append({
            "rule": rule, "series": series, "label": label, "kind": kind,
            "name": d["info"].get("eng_stage_name"), "stages": stage_ids,
        })
        print(f"category {rule} {label}: {len(stage_ids)} stages")

        for sid in stage_ids:
            b = c.page(board_path(rule, sid))
            if not b or not b.get("info"):
                print(f"  ! board {rule}/{sid} missing")
                continue
            if rule != 48 and int(b.get("rule") or 0) != rule:
                print(f"  ! board {rule}/{sid} returned rule {b.get('rule')}; skipped")
                continue
            users.update({u["userId"]: u["name"] for u in b.get("users", [])})
            info = stage_info(b["info"])
            stages_out[sid] = info
            posts = [norm_post(p) for p in b.get("posts") or []]
            posts.sort(key=lambda p: (p["rank"] or 10**9))
            low = lower_is_better(posts)
            changed += write_json(DATA / "boards" / f"{rule}-{sid}.json", {
                "rule": rule, "stage": sid, "lower_is_better": low, "posts": posts,
            })
            # extend WR history with the current #1s
            hpath = DATA / "history" / f"{rule}-{sid}.json"
            hist = read_json(hpath, {"rule": rule, "stage": sid, "records": []})
            tops = [wr_entry(p) for p in posts if p["rank"] == 1]
            hist["lower_is_better"] = low
            hist["records"] = merge_history(hist["records"], tops, low)
            changed += write_json(hpath, hist)
            changed += update_archive(rule, sid, posts)

    changed += sync_players(c, users)
    changed += write_json(DATA / "categories.json", categories_out)
    changed += write_json(DATA / "stages.json", {str(k): v for k, v in sorted(stages_out.items())})
    changed += write_json(DATA / "users.json", dict(sorted(users.items(), key=lambda kv: kv[0].lower())))
    write_json(DATA / "meta.json", {
        "source": BASE,
        "build_id": c.build_id,
        "synced_at": started.isoformat(timespec="seconds"),
    })
    print(f"done: {changed} files changed in {datetime.now(timezone.utc) - started}")


def archive_entry(p: dict) -> dict:
    keep = ("id", "user", "score", "date", "console", "video", "img", "comment")
    out = {k: p.get(k) for k in keep}
    if p.get("source"):  # where a run came from when it isn't a live pik5 sync
        out["source"] = p["source"]
    return out


def same_submission(x: dict, y: dict) -> bool:
    """Same player and score, dated within a day of each other (imported data
    has only a local date, pik5 a UTC timestamp)."""
    dx, dy = x.get("date"), y.get("date")
    if not dx or not dy:
        return True
    try:
        a = datetime.fromisoformat(dx.replace("Z", "+00:00"))
        b = datetime.fromisoformat(dy.replace("Z", "+00:00"))
    except ValueError:
        return dx[:10] == dy[:10]
    return abs((a - b).total_seconds()) <= 36 * 3600


def update_archive(rule: int, sid: int, posts: list[dict]) -> bool:
    """Keep every distinct submission ever seen for a board, so leaderboards can
    be reconstructed as of any date. Keyed by (player, score); the earliest
    date wins. If pik5 ever exposes full submission history, feed it in here."""
    path = DATA / "archive" / f"{rule}-{sid}.json"
    arc = read_json(path, {"rule": rule, "stage": sid, "posts": []})
    pool = {(a["user"], a["score"]): a for a in arc["posts"]}
    for p in posts:
        a = archive_entry(p)
        key = (a["user"], a["score"])
        old = pool.get(key)
        if old is None:
            pool[key] = a
            continue
        # Same run seen twice. An imported copy (it has a "source") only knows
        # the day, so a copy from pik5 itself within a day of it is the same
        # submission and wins: it has the post id, exact time and console.
        if same_submission(old, a) and bool(old.get("source")) != bool(a.get("source")):
            keep, other = (a, old) if old.get("source") else (old, a)
        elif (a["date"] or "") < (old["date"] or ""):
            keep, other = a, old
        else:
            keep, other = old, a
        for f in ("video", "img", "comment"):
            if not keep.get(f) and other.get(f):
                keep[f] = other[f]
        pool[key] = keep
    arc["posts"] = sorted(pool.values(), key=lambda a: (a["date"] or "", a["user"] or ""))
    return write_json(path, arc)


PROFILE_MAX_AGE_DAYS = 30
PROFILE_FETCH_LIMIT = 40  # per sync, to stay polite


def notable_players() -> list[str]:
    """Players worth a profile lookup: current #1s and the top 25 of each game."""
    wr: dict[str, int] = {}
    for f in (DATA / "boards").glob("*.json"):
        for p in read_json(f, {}).get("posts", []):
            if p.get("rank") == 1:
                wr[p["user"]] = wr.get(p["user"], 0) + 1
    out = sorted(wr, key=lambda u: -wr[u])
    for tid in SERIES_TOTALS.values():
        for r in read_json(DATA / "totals" / f"{tid}.json", {}).get("rows", [])[:25]:
            if r["user"] not in out:
                out.append(r["user"])
    return out


def sync_players(c: "Client", users: dict) -> bool:
    """Fetch pik5 profiles for notable players to find linked speedrun.com
    accounts, then read English name + country from speedrun.com's public API."""
    path = DATA / "players.json"
    players = read_json(path, {})
    now = datetime.now(timezone.utc)
    fetched = 0
    for uid in notable_players():
        prof = players.get(uid, {})
        age = (now - datetime.fromisoformat(prof["checked"])).days if prof.get("checked") else 10**6
        if age < PROFILE_MAX_AGE_DAYS:
            continue
        if fetched >= PROFILE_FETCH_LIMIT:
            break
        fetched += 1
        d = c.page(f"user/{uid}")
        if d is None:
            continue
        src = (d.get("userSettings") or {}).get("srcUserId")
        prof = {"checked": now.isoformat(timespec="seconds"), "src": src}
        if src:
            s = fetch(f"https://www.speedrun.com/api/v1/users/{src}", as_json=True)
            data = (s or {}).get("data") or {}
            prof["src_name"] = (data.get("names") or {}).get("international")
            prof["country"] = (((data.get("location") or {}).get("country") or {}).get("code") or "").lower() or None
        players[uid] = prof
    print(f"player profiles: {fetched} fetched, {len(players)} cached")
    return write_json(path, dict(sorted(players.items())))


def total_payload(d: dict, total_id: int) -> dict:
    rows = []
    for p in d.get("posts") or []:
        rows.append({
            "user": p.get("user_id"),
            "rank": p.get("post_rank"),
            "rps": p.get("rps"),
            "score": p.get("score"),
            "boards": len(p.get("ranks") or []),
            "date": p.get("created_at"),
        })
    rows.sort(key=lambda r: (r["rank"] or 10**9))
    return {"id": total_id, "name": (d.get("info") or {}).get("eng_stage_name"), "rows": rows}


# ---------------------------------------------------------------- backfill

def backfill(rules: list[int]):
    """Reconstruct WR progressions from pik5's year-end snapshots.

    A year snapshot lists every player's best as of that year, so the union of
    all snapshots, sorted by date with a running best, recovers nearly every WR
    (only a WR beaten by the same player within the same year can be missed).
    """
    cats = read_json(DATA / "categories.json", [])
    if not cats:
        sys.exit("run a regular sync first")
    if rules:
        cats = [c for c in cats if c["rule"] in rules]
    this_year = datetime.now(timezone.utc).year
    cl = Client()
    for cat in cats:
        rule = cat["rule"]
        if rule == 48:
            continue  # no yearly snapshots for the exam boards
        for sid in cat["stages"]:
            hpath = DATA / "history" / f"{rule}-{sid}.json"
            hist = read_json(hpath, {"rule": rule, "stage": sid, "records": []})
            board = read_json(DATA / "boards" / f"{rule}-{sid}.json", {})
            low = board.get("lower_is_better", hist.get("lower_is_better", False))
            cands = []
            seen = []
            for year in range(this_year - 1, FIRST_YEAR - 1, -1):
                d = cl.page(f"stage/{sid}/0/{rule}/{year}")
                posts = (d or {}).get("posts") or []
                if not posts:
                    break  # nothing earlier than this
                normed = [norm_post(p) for p in posts]
                seen += normed
                cands += [wr_entry(p) for p in normed]
            update_archive(rule, sid, seen)
            hist["lower_is_better"] = low
            hist["records"] = merge_history(hist["records"], cands, low)
            hist["backfilled"] = True
            write_json(hpath, hist)
            print(f"backfill {rule}/{sid}: {len(hist['records'])} WRs")


def players_only():
    """Refresh player profiles without a full board sync."""
    c = Client()
    users = read_json(DATA / "users.json", {})
    sync_players(c, users)


SRC_API = "https://www.speedrun.com/api/v1"


def src_runners():
    """Every runner with a run on any game in speedrun.com's Pikmin series,
    with the country they set on their profile. Saved to data/src_runners.json.
    About one request per 200 runs."""
    games = fetch(f"{SRC_API}/series/pikmin/games?max=50", as_json=True)["data"]
    runners: dict[str, dict] = {}
    for g in games:
        offset, n = 0, 0
        while True:
            d = fetch(f"{SRC_API}/runs?game={g['id']}&max=200&offset={offset}&embed=players", as_json=True)
            for run in d.get("data", []):
                for p in (run.get("players") or {}).get("data", []):
                    if p.get("rel") != "user":
                        continue
                    cc = (((p.get("location") or {}).get("country") or {}).get("code") or "").lower() or None
                    runners[p["id"]] = {"name": p["names"]["international"],
                                        "name_ja": p["names"].get("japanese"),
                                        "country": cc}
            n += len(d.get("data", []))
            if not any(l.get("rel") == "next" for l in d["pagination"].get("links", [])):
                break
            offset += 200
        print(f"  {g['names']['international']}: {n} runs")
    write_json(DATA / "src_runners.json", dict(sorted(runners.items(), key=lambda kv: kv[1]["name"].lower())))
    print(f"speedrun.com: {len(runners)} Pikmin runners")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if cmd == "backfill":
        backfill([int(a) for a in sys.argv[2:]])
    elif cmd == "players":
        players_only()
    elif cmd == "src":
        src_runners()
    else:
        sync()
