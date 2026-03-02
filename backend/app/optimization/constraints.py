"""FPL squad and formation constraint definitions and validators."""

from __future__ import annotations

from collections import Counter

# ---------------------------------------------------------------------------
# Formation rules
# ---------------------------------------------------------------------------

VALID_FORMATIONS: list[str] = [
    "3-4-3",
    "3-5-2",
    "4-3-3",
    "4-4-2",
    "4-5-1",
    "5-3-2",
    "5-4-1",
]

# Maps formation string -> {"GK": n, "DEF": n, "MID": n, "FWD": n}
FORMATION_RULES: dict[str, dict[str, int]] = {}
for _f in VALID_FORMATIONS:
    _parts = [int(x) for x in _f.split("-")]
    FORMATION_RULES[_f] = {
        "GK": 1,
        "DEF": _parts[0],
        "MID": _parts[1],
        "FWD": _parts[2],
    }

# Full squad composition (fixed by FPL rules)
SQUAD_COMPOSITION: dict[str, int] = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
SQUAD_SIZE = 15
MAX_PER_CLUB = 3
DEFAULT_BUDGET = 100.0  # in real-money units

# The FPL API uses "GKP" for goalkeepers; we normalise to "GK".
_POS_ALIAS: dict[str, str] = {"GKP": "GK"}


def _normalise_position(pos: str) -> str:
    """Normalise position strings (GKP -> GK)."""
    return _POS_ALIAS.get(pos, pos)


# ---------------------------------------------------------------------------
# Squad validator (15 players)
# ---------------------------------------------------------------------------

def validate_squad(
    players: list[dict],
    budget: float = DEFAULT_BUDGET,
) -> tuple[bool, list[str]]:
    """Validate a 15-player FPL squad.

    Parameters
    ----------
    players:
        List of player dicts, each with at least ``position`` (str),
        ``now_cost`` (int, in 0.1m units), and ``team`` or ``team_id`` (int).
    budget:
        Maximum budget in real-money units (e.g. 100.0 = 100m).

    Returns
    -------
    (valid, violations) where *valid* is True when the squad is legal.
    """
    violations: list[str] = []

    # --- squad size ---
    if len(players) != SQUAD_SIZE:
        violations.append(
            f"Squad must have exactly {SQUAD_SIZE} players, got {len(players)}"
        )

    # --- position counts ---
    pos_counts: Counter[str] = Counter()
    for p in players:
        pos = _normalise_position(p.get("position", ""))
        pos_counts[pos] += 1

    for pos, required in SQUAD_COMPOSITION.items():
        actual = pos_counts.get(pos, 0)
        if actual != required:
            violations.append(
                f"Need exactly {required} {pos} players, got {actual}"
            )

    # --- club limits ---
    club_counts: Counter[int] = Counter()
    for p in players:
        club = p.get("team") or p.get("team_id") or 0
        club_counts[club] += 1
    for club, count in club_counts.items():
        if count > MAX_PER_CLUB:
            violations.append(
                f"Max {MAX_PER_CLUB} players per club – team {club} has {count}"
            )

    # --- budget ---
    total_cost_raw = sum(p.get("now_cost", 0) for p in players)
    total_cost = total_cost_raw / 10.0  # convert 0.1m -> real money
    if total_cost > budget + 1e-6:
        violations.append(
            f"Total cost {total_cost:.1f}m exceeds budget {budget:.1f}m"
        )

    return (len(violations) == 0, violations)


# ---------------------------------------------------------------------------
# Starting XI validator
# ---------------------------------------------------------------------------

def validate_starting_xi(
    starters: list[dict],
    formation: str,
) -> tuple[bool, list[str]]:
    """Validate an 11-player starting XI against a formation.

    Parameters
    ----------
    starters:
        List of 11 player dicts (must include ``position``).
    formation:
        Formation string, e.g. ``"4-4-2"``.

    Returns
    -------
    (valid, violations)
    """
    violations: list[str] = []

    if formation not in FORMATION_RULES:
        violations.append(
            f"Invalid formation '{formation}'. "
            f"Valid formations: {', '.join(VALID_FORMATIONS)}"
        )
        return (False, violations)

    if len(starters) != 11:
        violations.append(f"Starting XI must have exactly 11 players, got {len(starters)}")

    required = FORMATION_RULES[formation]
    pos_counts: Counter[str] = Counter()
    for p in starters:
        pos = _normalise_position(p.get("position", ""))
        pos_counts[pos] += 1

    for pos, need in required.items():
        actual = pos_counts.get(pos, 0)
        if actual != need:
            violations.append(
                f"Formation {formation} requires {need} {pos}, got {actual}"
            )

    return (len(violations) == 0, violations)
