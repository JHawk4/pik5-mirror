"""How to turn a pik5 score into time used / time left.

Sources:
- Pikmin 4 Dandori Challenges: points = weight of everything delivered; if
  everything is collected, each remaining second adds 1 point (Pikipedia,
  "Dandori Challenge"). pik5's stage `treasure` is the collect-everything total.
- Pikmin 3 missions / side stories: if everything is collected, remaining time
  is added at a per-stage rate (Pikipedia, "Mission Mode"; values not listed).
  pik5's `treasure` is the platinum border, which equals the collect-everything
  total. Rates below were inferred from pik5's data: with these rates ~99% of
  scores on each board give a whole number of seconds within the time limit.
- Pikmin 1 All-Treasure / Max Score Time Attack (rule 11): pik5 stores
  treasure total + seconds left and displays it as time used
  (time limit + treasure - score; e.g. Impact Site 648 + 278 - 550 = 6:16).
- Pikmin 4 Trial of the Sage Leaf: pik5 stores seconds left; time limits from
  Pikipedia, "Trial of the Sage Leaf".
"""

# Pikmin 3: points per remaining second. Default 30; 10 on these stages
# (Battle Enemies! remix/DLC stages and the creature-hunting side stories).
P3_RATE_DEFAULT = 30
P3_RATE = {**{s: 10 for s in range(321, 331)}, 336: 10, 337: 10, 339: 10}
P3_RULES = {31, 32, 34, 36}

# Pikmin 4: 1 point per remaining second.
P4_RULES = {41, 44, 48}

# Pikmin 1 Max Score Time Attack: 1 point per remaining second, ranked by time used.
TIME_ATTACK_RULES = {11}

# Trial of the Sage Leaf time limits (seconds), stages 419-428.
SAGE_LIMITS = {419: 240, 420: 360, 421: 300, 422: 420, 423: 420,
               424: 240, 425: 60, 426: 240, 427: 300, 428: 300}


def bonus_rate(rule, sid):
    if rule in P3_RULES:
        return P3_RATE.get(sid, P3_RATE_DEFAULT)
    if rule in P4_RULES or rule in TIME_ATTACK_RULES:
        return 1
    return None


def time_limit(sid, stage):
    return (stage or {}).get("time") or SAGE_LIMITS.get(sid) or 0


def times(score, rule, sid, stage):
    """(time_used_s, time_left_s) or None when it can't be worked out.
    Scores below the collect-everything total mean the timer ran out."""
    rate = bonus_rate(rule, sid)
    stage = stage or {}
    limit = time_limit(sid, stage)
    total = stage.get("treasure") or 0
    if not rate or not limit or not total:
        return None
    if score < total:
        return limit, 0
    extra = score - total
    if extra % rate:
        return None
    left = extra // rate
    if left > limit:
        return None
    return limit - left, left
