"""Import historical runs from the old "P3 Scripts" Google Sheet scrape.

The sheet scraped the previous pik5 site (chr.mn/pik4) from 2007 to July 2023
and kept submissions that players later beat, which pik5 no longer shows.

Usage:
    python sync/import_sheet.py path/to/scrape.csv

The CSV is the sheet's "scrape" tab (columns Level, Score, Player, Date, Video,
Picutre, Comment). Download it with:
    https://docs.google.com/spreadsheets/d/1pCLeqvqmQE40fqJuxDf_AE506wPjWQocJF659SUS4OE/export?format=csv&gid=39135262

What it does:
- maps the old site's Pikmin 3 stage numbers to today's (Pikmin 2 is unchanged)
- converts shown times (time used) into pik5's stored form (seconds left)
- matches player names to today's pik5 ids; rows for names that no longer
  exist go to data/imports/sheet-unmatched.json for a manual decision
- adds each run to the stage's main-category archive (dedup by player+score,
  earliest date wins) and extends that board's WR history

Safe to re-run: already-present runs are left alone.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pik5_sync as S  # noqa: E402

# old site stage number -> current pik5 stage id (Pikmin 3 only), inferred by
# matching identical (player, score) runs between the sheet and today's boards
P3_OLD_TO_NEW = {
    301: 301, 302: 302, 303: 303, 304: 304, 305: 305,
    306: 316, 307: 317, 308: 318, 309: 319, 310: 320,
    311: 345, 312: 346, 313: 347, 314: 348, 315: 349, 316: 350,
    317: 306, 318: 307, 319: 308, 320: 309, 321: 310,
    322: 321, 323: 322, 324: 323, 325: 324, 326: 325,
    327: 311, 328: 312, 329: 313, 330: 314, 331: 315,
    332: 326, 333: 327, 334: 328, 335: 329, 336: 330,
    349: 331, 350: 332, 351: 333, 352: 334, 353: 335, 354: 336,
    355: 337, 356: 338, 357: 339, 358: 340, 359: 341, 360: 342,
    361: 343, 362: 344,
}
# pik5's stored limit is wrong for this stage; pik5 itself displays on a 15:00 basis
LIMIT_FIX = {346: 900}
# main (1P) category for each stage, preferred over special categories
MAIN_RULES = (21, 22, 31, 32, 33, 36)
SOURCE = "sheet-2023"


def secs(text: str) -> int:
    parts = [int(x) for x in text.split(":")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


def main(csv_path: str):
    D = S.DATA
    users = S.read_json(D / "users.json", {})
    name_to_uid: dict[str, str] = {}
    for uid, name in users.items():
        name_to_uid.setdefault(name, uid)
        name_to_uid.setdefault(uid, uid)
    stages = S.read_json(D / "stages.json", {})
    cats = S.read_json(D / "categories.json", [])
    rule_of: dict[int, int] = {}
    for c in cats:
        if c["rule"] in MAIN_RULES:
            for sid in c["stages"]:
                rule_of.setdefault(int(sid), c["rule"])

    by_board: dict[tuple[int, int], list[dict]] = {}
    unmatched, skipped = [], 0
    for r in csv.DictReader(open(csv_path, encoding="utf-8")):
        old = int(r["Level"])
        sid = P3_OLD_TO_NEW.get(old, old) if old // 100 == 3 else old
        st = stages.get(str(sid)) or {}
        rule = rule_of.get(sid)
        if not rule:
            skipped += 1
            continue
        raw = r["Score"].strip()
        if ":" in raw:  # sheet shows time used; pik5 stores seconds left
            limit = LIMIT_FIX.get(sid) or st.get("time") or 0
            score = limit - secs(raw) if st.get("display") == "time" and limit else secs(raw)
        else:
            score = int(raw.replace(",", ""))
        img = (r.get("Picutre") or "").rstrip("/").rsplit("/", 1)[-1]
        post = {
            "id": None, "user": name_to_uid.get(r["Player"]), "score": score,
            "date": f'{r["Date"]}T00:00:00.000000Z' if r["Date"] else None,
            "console": None, "video": (r.get("Video") or "").strip(), "img": img,
            "comment": r.get("Comment") or "", "source": SOURCE,
        }
        if not post["user"]:
            unmatched.append({**post, "name": r["Player"], "rule": rule, "stage": sid})
            continue
        by_board.setdefault((rule, sid), []).append(post)

    # A run better than today's record can't be a beaten personal best: it's a
    # typo that was later corrected (e.g. 15840 vs 15480) or a run from another
    # category. Hold those for review instead of importing them.
    rejected = []
    for (rule, sid), posts in by_board.items():
        board = S.read_json(D / "boards" / f"{rule}-{sid}.json", {})
        cur = [p["score"] for p in board.get("posts", [])]
        if not cur:
            continue
        low = board.get("lower_is_better", False)
        wr = min(cur) if low else max(cur)
        keep = []
        for p in posts:
            if (p["score"] < wr) if low else (p["score"] > wr):
                rejected.append({**p, "rule": rule, "stage": sid, "why": f"beats current record {wr}"})
            else:
                keep.append(p)
        posts[:] = keep

    added = 0
    for (rule, sid), posts in sorted(by_board.items()):
        path = D / "archive" / f"{rule}-{sid}.json"
        before = len(S.read_json(path, {"posts": []})["posts"])
        S.update_archive(rule, sid, posts)
        after = S.read_json(path, {"posts": []})
        added += len(after["posts"]) - before
        # extend the WR progression with everything now known for the board
        hpath = D / "history" / f"{rule}-{sid}.json"
        hist = S.read_json(hpath, {"rule": rule, "stage": sid, "records": []})
        low = S.read_json(D / "boards" / f"{rule}-{sid}.json", {}).get("lower_is_better", False)
        cands = [S.wr_entry(p) for p in after["posts"]]
        hist["records"] = S.merge_history(hist["records"], cands, low)
        hist["lower_is_better"] = low
        S.write_json(hpath, hist)

    S.write_json(D / "imports" / "sheet-unmatched.json", unmatched)
    S.write_json(D / "imports" / "sheet-rejected.json", rejected)
    print(f"boards touched {len(by_board)}, runs added {added}, "
          f"unmatched-name rows {len(unmatched)}, rejected (beat current record) {len(rejected)}, "
          f"rows with no main category {skipped}")


if __name__ == "__main__":
    main(sys.argv[1])
