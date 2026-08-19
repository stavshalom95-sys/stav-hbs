#!/usr/bin/env python3
"""
Fetch Hapoel Beer Sheva starting lineups from football.org.il match-report pages
and format them for the "הרכב פותח לב\"ש" column of the stav-hbs summary sheet.

Usage:
    python scripts/parse_lineups.py <match_url_or_game_id> [<match_url_or_game_id> ...]

    Each argument may be either a full match URL
    (https://www.football.org.il/leagues/games/game/?game_id=NNNNNN) or a bare
    game_id. For each match, prints the game_id followed by the 4-line lineup
    block (see format notes below), ready to paste into the sheet.

Must run from a normal outbound environment (e.g. a developer machine or
Claude's own sandbox) — football.org.il blocks Google Apps Script's outbound
IPs with HTTP 403, so this cannot be run as a bound Apps Script function.

Output format (exactly 4 lines, no position headers, no blank lines):
    line 1: goalkeeper (short name only)
    line 2: defenders, comma-separated
    line 3: midfielders, comma-separated
    line 4: forwards, comma-separated
A substitute is written in parentheses immediately after the starter they
replaced, e.g. "ויטור (בלוריאן)".

Unknown players: if a starting-XI or substitute name isn't in NAME_MAP below,
the script prints it as unmapped and exits non-zero. Ask the user for the
short name and position group (GK/DEF/MID/ATT), then add the entry to
NAME_MAP permanently before re-running.
"""

import re
import sys
import urllib.request

BEER_SHEVA_TEAM_ID = "2171"
BEER_SHEVA_LITERAL_NAME = "הפועל באר שבע"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Full name (as it appears on football.org.il) -> (short name, position group)
# Position groups: GK, DEF, MID, ATT
NAME_MAP = {
    # GK
    "ניב אליאסי": ("אליאסי", "GK"),
    "אופיר מרציאנו": ("מרציאנו", "GK"),
    "מרקו וולף": ("וולף", "GK"),
    # DEF
    "גיא מזרחי": ("מזרחי", "DEF"),
    "מתן בלטקסה": ("בלטקסה", "DEF"),
    "מיגל אנג'לו לאונרדו ויטור": ("ויטור", "DEF"),
    "הלדר פיליפ אוליביירה לופז": ("לופז", "DEF"),
    "אור בלוריאן": ("בלוריאן", "DEF"),
    "ג'יבריל דיופ": ("דיופ", "DEF"),
    "אופיר דודזאדה": ("דודזאדה", "DEF"),
    "רועי לוי": ("רועי לוי", "DEF"),
    "יואן סטויאנוב": ("סטויאנוב", "DEF"),
    # MID
    "שי אליאס": ("אליאס", "MID"),
    "לוקאס דה סוזה ונטורה": ("ונטורה", "MID"),
    "דן ביטון": ("דן ביטון", "MID"),
    "אמיר חיים גנאח": ("גנאח", "MID"),
    "קינגס קאוגנה": ("קאנגווה", "MID"),
    "אליאל פרץ": ("פרץ", "MID"),
    "מוחמד כנעאן": ("כנעאן", "MID"),
    "מוחמד אבו רומי": ("אבו רומי", "MID"),
    "איתי חזות": ("חזות", "MID"),
    "זאהי אחמד": ("אחמד", "MID"),
    "סמיר פרהוד": ("פרהוד", "MID"),
    "יואב קורן": ("קורן", "MID"),
    "מור סמן טוב": ("סימן טוב", "MID"),
    "יונתן גלבוע": ("גלבוע", "MID"),
    "יונתן גרינבאום": ("גרינבאום", "MID"),
    # ATT
    "אלון תורגמן": ("תורג'מן", "ATT"),
    "איגור זלאטנוביץ": ("זלאטנוביץ'", "ATT"),
    "ג'בון רומריו איסט": ("איסט", "ATT"),
    "עמית אוחנה": ("אוחנה", "ATT"),
    "אילון אלמוג": ("אלמוג", "ATT"),
    # Sub-only so far (no starting appearance seen yet; position unknown)
    "ג'וזף סבובו בנדה": ("סבובו", None),
    "פול ארנולד גריטה": ("גריטה", None),
}

POSITION_ORDER = ["GK", "DEF", "MID", "ATT"]


class ParseError(Exception):
    pass


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def to_url(arg: str) -> str:
    if arg.startswith("http"):
        return arg
    return f"https://www.football.org.il/leagues/games/game/?game_id={arg}"


def determine_side(html: str) -> str:
    """Return 'home' or 'guest' — whichever side is Beer Sheva."""
    home_match = re.search(r"team-home[\s\S]{0,400}?team_id=(\d+)", html)
    guest_match = re.search(r"team-guest[\s\S]{0,400}?team_id=(\d+)", html)
    if home_match and home_match.group(1) == BEER_SHEVA_TEAM_ID:
        return "home"
    if guest_match and guest_match.group(1) == BEER_SHEVA_TEAM_ID:
        return "guest"
    raise ParseError("Could not find Beer Sheva (team_id=2171) as home or guest")


def slice_block(html: str, side: str, marker_class: str) -> str:
    """
    Slice out the <div class="{side} {marker_class}"> block for `side`,
    bounded by whichever comes first: the next <div class="title"> or the
    other side's same marker (the two sides' blocks often sit back-to-back
    with no title in between).
    """
    other_side = "guest" if side == "home" else "home"
    start_pat = re.compile(rf'<div class="{side} {marker_class}[^"]*"')
    start_match = start_pat.search(html)
    if not start_match:
        raise ParseError(f"Could not find {side} {marker_class} block")
    start = start_match.end()

    other_pat = re.compile(rf'<div class="{other_side} {marker_class}[^"]*"')
    title_pat = re.compile(r'<div class="title">')

    other_match = other_pat.search(html, start)
    title_match = title_pat.search(html, start)

    candidates = [m.start() for m in (other_match, title_match) if m]
    end = min(candidates) if candidates else len(html)
    return html[start:end]


NAME_SPAN_RE = re.compile(r'<span class="name"><b>([^<]+)</b>([^<]*)</span>')


def parse_players(block_html: str):
    """Return list of (name, is_gk) for every player in a lineup block."""
    players = []
    for name, suffix in NAME_SPAN_RE.findall(block_html):
        name = name.strip()
        is_gk = "GK" in suffix
        players.append((name, is_gk))
    return players


def parse_starting_xi(html: str, side: str):
    block = slice_block(html, side, "Active clearfix")
    players = parse_players(block)
    if len(players) != 11:
        raise ParseError(f"Expected 11 starters, found {len(players)}: {players}")
    gk_count = sum(1 for _, is_gk in players if is_gk)
    if gk_count != 1:
        raise ParseError(f"Expected exactly 1 GK, found {gk_count}")
    return players


TIMELINE_NODE_RE = re.compile(
    r"<div class='node playerout [^']*change'>([\s\S]*?)</div>\s*(?=<div class='node|\Z)"
)
TEAM_RE = re.compile(r"<div class='team'>([^<]+)</div>")
PLAYER_OUT_RE = re.compile(r"<div class='player PlayerOut'>([\s\S]*?)</div>")
PLAYER_IN_RE = re.compile(r"<div class='player PlayerIn'>([\s\S]*?)</div>")
NAME_NUM_RE = re.compile(r"([^\(]+)\(\d+\)")


def _clean_player_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw).strip()
    m = NAME_NUM_RE.search(text)
    return (m.group(1) if m else text).strip()


def parse_substitutions(html: str):
    """
    Return {out_name: in_name} for every Beer Sheva substitution, read from
    the id='gameMoves' timeline (exact pairing, unambiguous even for
    same-minute multi-swaps) — do NOT use the change-down/change-up minutes
    in the lineup blocks, which cannot disambiguate simultaneous swaps.
    """
    moves_match = re.search(r"id='gameMoves'([\s\S]*)", html)
    if not moves_match:
        moves_match = re.search(r'id="gameMoves"([\s\S]*)', html)
    if not moves_match:
        return {}
    timeline = moves_match.group(1)

    subs = {}
    for node in TIMELINE_NODE_RE.findall(timeline):
        team_match = TEAM_RE.search(node)
        if not team_match or team_match.group(1).strip() != BEER_SHEVA_LITERAL_NAME:
            continue
        outs = PLAYER_OUT_RE.findall(node)
        ins = PLAYER_IN_RE.findall(node)
        for out_raw, in_raw in zip(outs, ins):
            out_name = _clean_player_text(out_raw)
            in_name = _clean_player_text(in_raw)
            subs[out_name] = in_name
    return subs


def map_name(raw_name: str):
    entry = NAME_MAP.get(raw_name)
    if entry is None:
        return None
    return entry


def build_lineup(starters, subs_raw):
    """
    starters: list of (raw_name, is_gk)
    subs_raw: {raw_out_name: raw_in_name}
    Returns the 4-line formatted lineup string, or raises ParseError listing
    any unmapped names.
    """
    unmapped = set()
    groups = {pos: [] for pos in POSITION_ORDER}
    gk_line = None

    for raw_name, is_gk in starters:
        mapped = map_name(raw_name)
        if mapped is None:
            unmapped.add(raw_name)
            continue
        short, position = mapped
        if position is None:
            unmapped.add(f"{raw_name} (position unknown)")
            continue

        display = short
        if raw_name in subs_raw:
            sub_raw = subs_raw[raw_name]
            sub_mapped = map_name(sub_raw)
            if sub_mapped is None:
                unmapped.add(sub_raw)
            else:
                display = f"{short} ({sub_mapped[0]})"

        if is_gk:
            gk_line = display
        else:
            groups[position].append(display)

    if unmapped:
        raise ParseError(
            "Unmapped player(s): " + ", ".join(sorted(unmapped)) +
            " — add short name + position group to NAME_MAP and re-run."
        )
    if gk_line is None:
        raise ParseError("No goalkeeper found among starters")

    lines = [gk_line]
    for pos in ("DEF", "MID", "ATT"):
        lines.append(", ".join(groups[pos]))
    return "\n".join(lines)


def process_match(arg: str) -> str:
    url = to_url(arg)
    html = fetch_html(url)
    side = determine_side(html)
    starters = parse_starting_xi(html, side)
    subs_raw = parse_substitutions(html)
    return build_lineup(starters, subs_raw)


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
