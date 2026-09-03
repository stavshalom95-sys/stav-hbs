#!/usr/bin/env python3
"""
Fetch Hapoel Beer Sheva starting lineups from Transfermarkt match-sheet
pages (used for European matches not covered by football.org.il) and format
them for the same "הרכב פותח לב\"ש" column as scripts/parse_lineups.py.

Usage:
    python scripts/parse_lineups_transfermarkt.py <match_url_or_id> [...]

    Each argument may be a full Transfermarkt match-sheet URL
    (e.g. https://www.transfermarkt.com/hapoel-beer-sheva_red-star-belgrade/
    index/spielbericht/4973494) or a bare numeric spielbericht id.

Shares scripts/parse_lineups.py's NAME_MAP as the single source of truth for
short-name/position mappings, since Beer Sheva players appear across both
domestic (football.org.il) and European (Transfermarkt) competitions. The
dict key here is whatever display name Transfermarkt uses for that player in
its formation view (often just a surname, e.g. "Baltaxa", but sometimes
fuller, e.g. "Miguel Vítor") — this is NOT the same string football.org.il
uses, so a player already mapped from a domestic match still needs a new
NAME_MAP entry the first time they show up in a Transfermarkt match, even
though the (short_name, position) value will usually be identical. Do not
auto-alias by fuzzy surname matching — ask the user to confirm, same as any
new name (see parse_lineups.py's "don't guess" rule). When asking, this
script includes Transfermarkt's own position code (from the substitutes
table) as a hint, but the user's answer is still authoritative.

Output format: identical to parse_lineups.py (single-line, " / "-separated
GK / DEF / MID / ATT groups, subs in parentheses after the starter they
replaced) — see that file's docstring for the exact spec.
"""

import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
from parse_lineups import NAME_MAP, build_lineup, map_name, ParseError  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BEER_SHEVA_CLUB_ID = "2976"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def to_url(arg: str) -> str:
    if arg.startswith("http"):
        return arg
    return f"https://www.transfermarkt.com/spielbericht/index/spielbericht/{arg}"


TEAM_HEADER_RE = re.compile(
    r'<div class="unterueberschrift aufstellung-unterueberschrift-mannschaft[^"]*">'
)


def split_team_blocks(html: str):
    """
    Return (block1, block2): the two teams' full formation+bench HTML
    chunks, split at the two "aufstellung-unterueberschrift-mannschaft" team
    header markers that appear on a published match sheet.
    """
    starts = [m.start() for m in TEAM_HEADER_RE.finditer(html)]
    if len(starts) < 2:
        raise ParseError(
            "Could not find two team lineup blocks — lineups may not be "
            "published yet for this match"
        )
    block1 = html[starts[0]:starts[1]]
    block2 = html[starts[1]:]
    return block1, block2


def determine_beer_sheva_block(block1: str, block2: str) -> str:
    # Only look at each block's own team-header (right at its start) — the
    # rest of a block can be very long and mention the other club too (e.g.
    # in substitute profile links, related content), so checking the whole
    # block risks a false "both/neither" match.
    marker = f"verein/{BEER_SHEVA_CLUB_ID}/"
    in1, in2 = marker in block1[:600], marker in block2[:600]
    if in1 and not in2:
        return block1
    if in2 and not in1:
        return block2
    raise ParseError(
        f"Could not uniquely identify the Beer Sheva (club {BEER_SHEVA_CLUB_ID}) "
        "lineup block"
    )


PLAYER_CONTAINER_SPLIT_RE = re.compile(r'(?=<div class="formation-player-container")')
NAME_LINK_RE = re.compile(r'<a href="/[^"]+/profil/spieler/(\d+)">([^<]+)</a>')
TOP_PCT_RE = re.compile(r'top:\s*([\d.]+)%')
SUB_OUT_ICON_RE = re.compile(
    r"icon-auswechslung-formation[\s\S]*?data-content=\"[^\"]*?/(\d+)\""
)


def parse_starters(block: str):
    """Return [(player_id, name, top_pct, sub_out_event_id_or_None), ...]."""
    pitch_end = block.find('class="ersatzbank"')
    pitch_html = block[:pitch_end] if pitch_end != -1 else block
    chunks = PLAYER_CONTAINER_SPLIT_RE.split(pitch_html)
    starters = []
    for chunk in chunks:
        name_m = NAME_LINK_RE.search(chunk)
        if not name_m:
            continue
        pid, name = name_m.group(1), name_m.group(2).strip()
        top_m = TOP_PCT_RE.search(chunk)
        top_pct = float(top_m.group(1)) if top_m else 0.0
        sub_m = SUB_OUT_ICON_RE.search(chunk)
        sub_out_id = sub_m.group(1) if sub_m else None
        starters.append((pid, name, top_pct, sub_out_id))
    if not starters:
        raise ParseError("No starters found in lineup block")
    return starters


SUB_ROW_RE = re.compile(
    r'<td class="nummer formation-number-substitute">[\s\S]*?</td>\s*'
    r'<td>\s*<a title="[^"]*" href="/[^"]+/profil/spieler/(\d+)">([^<]+)</a>'
    r'([\s\S]*?)</td>\s*'
    r'<td>\s*([A-Za-z]*)\s*</td>'
)
SUB_IN_ICON_RE = re.compile(
    r"icon-einwechslung-formation[\s\S]*?data-content=\"[^\"]*?/(\d+)\""
)


def parse_bench(block: str):
    """Return [(player_id, name, position_code, sub_in_event_id_or_None), ...]."""
    bench_start = block.find('class="ersatzbank"')
    bench_html = block[bench_start:] if bench_start != -1 else ""
    bench = []
    for m in SUB_ROW_RE.finditer(bench_html):
        pid, name, extra, pos_code = m.groups()
        in_m = SUB_IN_ICON_RE.search(extra)
        sub_in_id = in_m.group(1) if in_m else None
        bench.append((pid, name.strip(), pos_code.strip(), sub_in_id))
    return bench


# Transfermarkt position codes -> our GK/DEF/MID/ATT buckets, for the
# position *hint* shown alongside an unmapped substitute's name (the user's
# answer is still what actually gets used).
POSITION_CODE_HINTS = {
    "GK": "GK",
    "SW": "DEF", "CB": "DEF", "LB": "DEF", "RB": "DEF",
    "LWB": "DEF", "RWB": "DEF", "DF": "DEF",
    "DM": "MID", "CM": "MID", "AM": "MID", "LM": "MID", "RM": "MID", "MF": "MID",
    "LW": "ATT", "RW": "ATT", "CF": "ATT", "SS": "ATT", "ST": "ATT", "FW": "ATT",
}

# "Biton"/"Bitton" is genuinely ambiguous on Transfermarkt — could be אורן
# ביטון (DEF) or דן ביטון (MID) — see the two synthetic "Biton (DEF)" /
# "Biton (MID)" NAME_MAP keys. Per the user's explicit instruction, resolve
# by the player's actual position in *this* match rather than guessing:
# starters are classified by how deep they sit in the pitch diagram (the
# defensive line sits at top% >= ~48 in every formation seen so far),
# substitutes by Transfermarkt's own explicit position code.
BITON_RAW_NAMES = {"Biton", "Bitton"}
BITON_STARTER_DEF_THRESHOLD = 48.0


def resolve_biton(starters, bench):
    def starter_key(name, top_pct):
        if name not in BITON_RAW_NAMES:
            return name
        return "Biton (DEF)" if top_pct >= BITON_STARTER_DEF_THRESHOLD else "Biton (MID)"

    def bench_key(name, pos_code):
        if name not in BITON_RAW_NAMES:
            return name
        bucket = POSITION_CODE_HINTS.get(pos_code)
        if bucket == "DEF":
            return "Biton (DEF)"
        if bucket in ("MID", "ATT"):
            return "Biton (MID)"
        return name  # unresolvable — falls through to a normal unmapped error

    starters = [
        (pid, starter_key(name, top_pct), top_pct, sub_out_id)
        for pid, name, top_pct, sub_out_id in starters
    ]
    bench = [
        (pid, bench_key(name, pos_code), pos_code, sub_in_id)
        for pid, name, pos_code, sub_in_id in bench
    ]
    return starters, bench


def process_match(arg: str) -> str:
    url = to_url(arg)
    html = fetch_html(url)
    block1, block2 = split_team_blocks(html)
    block = determine_beer_sheva_block(block1, block2)

    starters = parse_starters(block)
    bench = parse_bench(block)
    starters, bench = resolve_biton(starters, bench)

    # The goalkeeper sits deepest in Transfermarkt's pitch diagram (max top%)
    # regardless of formation — more robust than relying on shirt number 1.
    gk_id = max(starters, key=lambda s: s[2])[0]

    sub_out_by_event = {sid: name for _, name, _, sid in starters if sid}
    subs_raw = {}
    for _, name, _, in_event in bench:
        if in_event and in_event in sub_out_by_event:
            subs_raw[sub_out_by_event[in_event]] = name

    starters_for_build = [(name, pid == gk_id) for pid, name, _, _ in starters]

    try:
        return build_lineup(starters_for_build, subs_raw)
    except ParseError as exc:
        msg = str(exc)
        hints = []
        for _, name, pos_code, _ in bench:
            if map_name(name) is None and name in msg:
                bucket = POSITION_CODE_HINTS.get(pos_code, "?")
                hints.append(f"{name} (Transfermarkt lists position: {pos_code} -> likely {bucket})")
        if hints:
            raise ParseError(msg + " | position hints: " + "; ".join(hints))
        raise


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    exit_code = 0
    for arg in argv:
        print(f"=== {arg} ===")
        try:
            print(process_match(arg))
        except (ParseError, urllib.error.URLError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            exit_code = 1
        print()
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
