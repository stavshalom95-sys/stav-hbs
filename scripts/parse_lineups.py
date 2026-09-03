#!/usr/bin/env python3
"""
Fetch Hapoel Beer Sheva starting lineups from football.org.il match-report pages
and format them for the "הרכב פותח לב\"ש" column of the stav-hbs summary sheet.

Usage:
    python scripts/parse_lineups.py <match_url_or_game_id> [<match_url_or_game_id> ...]

    Each argument may be either a full match URL
    (https://www.football.org.il/leagues/games/game/?game_id=NNNNNN) or a bare
    game_id. For each match, prints the game_id followed by the single-line
    lineup string (see format notes below), ready to paste into the sheet.

Must run from a normal outbound environment (e.g. a developer machine or
Claude's own sandbox) — football.org.il blocks Google Apps Script's outbound
IPs with HTTP 403, so this cannot be run as a bound Apps Script function.

Output format: a single line, four position groups separated by " / "
(no position headers):
    group 1: goalkeeper (short name only)
    group 2: defenders, comma-separated
    group 3: midfielders, comma-separated
    group 4: forwards, comma-separated
A substitute is written in parentheses immediately after the starter they
replaced, e.g. "ויטור (בלוריאן)". Kept on one line (rather than one cell
line per group) so sheet rows stay compact; the dashboard reconstructs the
per-group line breaks for display by splitting on " / ".

Unknown players: if a starting-XI or substitute name isn't in NAME_MAP below,
the script prints it as unmapped and exits non-zero. Ask the user for the
short name and position group (GK/DEF/MID/ATT), then add the entry to
NAME_MAP permanently before re-running.
"""

import re
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

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
    "איתן טיבי": ("טיבי", "DEF"),
    "קרלוס דוס סנטוס רודריגז פונק": ("פונק", "DEF"),
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
    "אנטוניו ולנטין ספר": ("ספר", "MID"),
    "לוקאס מריאנו בריירו": ("בריירו", "MID"),
    "רועי גורדנה": ("גורדנה", "MID"),
    "יורי חוסה פיקנצ'ו מדיירוש": ("מדיירוש", "MID"),
    "תומר יוספי": ("יוספי", "MID"),
    # ATT
    "אלון תורגמן": ("תורג'מן", "ATT"),
    "איגור זלאטנוביץ": ("זלאטנוביץ'", "ATT"),
    "ג'בון רומריו איסט": ("איסט", "ATT"),
    "עמית אוחנה": ("אוחנה", "ATT"),
    "אילון אלמוג": ("אלמוג", "ATT"),
    "רותם חטואל": ("חטואל", "ATT"),
    "פול ארנולד גריטה": ("גריטה", "ATT"),
    # GK (301-491 historical batch)
    "אוהד לויטה": ("לויטה", "GK"),
    "אריאל הרוש": ("הרוש", "GK"),
    "ארנסטאס סטקוס": ("סטקוס", "GK"),
    "עומרי גלזר": ("גלזר", "GK"),
    # DEF (301-491 historical batch)
    "אביב סולומון": ("סולומון", "DEF"),
    "אוהד לביא": ("לביא", "DEF"),
    "אור דדיה": ("דדיה", "DEF"),
    "אורן ביטון": ("ביטון", "DEF"),
    "איתן רצון": ("רצון", "DEF"),
    "אמיר משה אריאלי": ("אריאלי", "DEF"),
    "ארי מרנשטין": ("מרנשטיין", "DEF"),
    "בן ביטון": ("ביטון", "DEF"),
    "בן תורג'מן": ("תורג'מן", "DEF"),
    "דודו טויטו": ("טויטו", "DEF"),
    "דור אלו": ("אלו", "DEF"),
    "הראל שלום": ("שלום", "DEF"),
    "חאתם אלחמיד": ("אלחמיד", "DEF"),
    "לואי טאהא": ("טאהא", "DEF"),
    "מיחאלי קורהוט": ("קורהוט", "DEF"),
    "מקסימו לוי": ("לוי", "DEF"),
    "מתן אוחיון": ("אוחיון", "DEF"),
    "ניב פליטר": ("פליטר", "DEF"),
    "עבדול קודוס קוליבאלי": ("קוליבאלי", "DEF"),
    "עמית ביטון": ("ביטון", "DEF"),
    "שון גולדברג": ("גולדברג", "DEF"),
    "שיר צדק": ("צדק", "DEF"),
    "שמואל בנימין אליאס שיימן": ("שיימן", "DEF"),
    # MID (301-491 historical batch)
    "אוגוצ'וקאו ג'ון הוגו": ("אוגו", "MID"),
    "איליי מדמון": ("מדמון", "MID"),
    "אלטון אופיי אקולטסה": ("אקולטסה", "MID"),
    "אנדרה ביוגו פוקו": ("פוקו", "MID"),
    "אנדרה רנאטו סוארס מרטינס": ("מרטינס", "MID"),
    "אריק סבו": ("סאבו", "MID"),
    "ג'וז'ואה פליפה סוארס פסקאוורה": ("ג'וז'ואה", "MID"),
    "ג'וליאן וויליאם סטואט": ("סטו", "MID"),
    "ג'ימי וילצ'ז מארין": ("מארין", "MID"),
    "גוסטבו מרמנטיני דוס סאנטוס": ("מרמנטיני", "MID"),
    "גיא בדש": ("בדש", "MID"),
    "דוד יאיר קלטינס": ("קלטינס", "MID"),
    "דויד מרטינס סימאו": ("סימאו", "MID"),
    "דור מיכה": ("מיכה", "MID"),
    "דיינר אלכסנדר קיניונס": ("קיניונס", "MID"),
    "דן איינבינדר": ("איינבינדר", "MID"),
    "דנילו מורנו אספרייה": ("אספרייה", "MID"),
    "ויירה רוסה פארליי": ("רוסה", "MID"),
    "חן עזרא": ("עזרא", "MID"),
    "חנן ממן": ("ממן", "MID"),
    "כריסטופר פאול פטרסון": ("פטרסון", "MID"),
    "מאגומד שאפי סוליימאנוב": ("סולימאנוב", "MID"),
    "מאור מליקסון": ("מליקסון", "MID"),
    "מיכאל אוחנה": ("אוחנה", "MID"),
    "מרואן קבהא": ("קבהא", "MID"),
    "נאור סבג": ("סבג", "MID"),
    "ניב זריהן": ("זריהן", "MID"),
    "נתנאל אסקיאס": ("אסקיאס", "MID"),
    "סזאר מרסלו מלי": ("מרסלו מלי", "MID"),
    "סינטאיהו סלליך": ("סלליך", "MID"),
    "עדן שמיר": ("שמיר", "MID"),
    "עומאר אולאד אימראן": ("עומאר", "MID"),
    "פטרוצי דויד": ("פטרוצי", "MID"),
    "קווין גיא-נואל פייר טפוקו": ("טפוקו", "MID"),
    "קונסטנטין אדריאן פאון אלכסנדרו": ("פאון", "MID"),
    "רועי גבריאל ממן": ("ממן", "MID"),
    "רמזי ספורי": ("ספורי", "MID"),
    "שגיב יחזקאל": ("יחזקאל", "MID"),
    # ATT (301-491 historical batch)
    "איתי שכטר": ("שכטר", "ATT"),
    "אסטריט סלמאני": ("סלמאני", "ATT"),
    "ארתור שושנאצב": ("שושנאצב", "ATT"),
    "בן שהר": ("שהר", "ATT"),
    "ג'ונתן אלכסנדר אגודלו ולאסקז": ("אגודלו", "ATT"),
    "גטן אנתוני וורן": ("וארן", "ATT"),
    "גיא מלמד": ("מלמד", "ATT"),
    "דיא סבע": ("סבע", "ATT"),
    "חוסה אנחל קאריו": ("קריו", "ATT"),
    "יוג'ין אנסה": ("אנסה", "ATT"),
    "נייג'ל האסלבנק": ("האסלבנק", "ATT"),
    "ניקיטה רוקאביציה": ("רוקאביציה", "ATT"),
    "עדן בן בסט": ("בן בסט", "ATT"),
    "פטריק קלימלה": ("קלימלה", "ATT"),
    "קייס גאנם": ("גאנם", "ATT"),
    "תומר חמד": ("חמד", "ATT"),
    # 301-491 historical batch, round 2 (subs revealed after their starter's own mapping unblocked them)
    "יונתן אליאס": ("אליאס", "MID"),
    "בנימין נתן": ("בנימין", "MID"),
    "גל לוי": ("לוי", "MID"),
    "רואי אביטן": ("אביטן", "MID"),
    "מוחמד גדיר": ("גדיר", "ATT"),
    "עבדאלה אבו עאבד": ("אבו עבאד", "ATT"),
    "איתמר שבירו": ("שבירו", "ATT"),
    "נועם שחר": ("שחר", "ATT"),
    # Sub-only so far (no starting appearance seen yet; position unknown)
    "ג'וזף סבובו בנדה": ("סבובו", None),
    # GK (138-294 historical batch, 2013-2019 squad era)
    "אוסטין אמאמצ'וקו אג'ידה": ("אג'ידה", "GK"),
    "גיא חיימוב": ("חיימוב", "GK"),
    "דוד גורש": ("גורש", "GK"),
    "רובי לבקוביץ'": ("לבקוביץ'", "GK"),
    # DEF (138-294 historical batch)
    "אביתר אילוז": ("אילוז", "DEF"),
    "דור מלול": ("מלול", "DEF"),
    "וויליאם סוארס": ("סוארס", "DEF"),
    "טומיסלב פיוביץ'": ("פיוביץ'", "DEF"),
    "יואכים דניאל אסקלינג": ("אסקלינג", "DEF"),
    # MID (138-294 historical batch)
    "אובידיו סטפן הובאן": ("הובאן", "MID"),
    "אנתוני ננדוזו נוואקמה": ("נוואקמה", "MID"),
    "גל אראל": ("אראל", "MID"),
    "ולדימיר ברואון": ("בראון", "MID"),
    "חואן-איסאק קוואנקה-לופז": ("קוואנקה", "MID"),
    "יובל שבתאי": ("שבתאי", "MID"),
    "מאור בוזגלו": ("בוזגלו", "MID"),
    "מהראן ראדי": ("ראדי", "MID"),
    "סראג' נסאר": ("נסאר", "MID"),
    "עילאי טרוסט": ("טרוסט", "MID"),
    # ATT (138-294 historical batch)
    "אליניב ברדה": ("ברדה", "ATT"),
    "דובב גבאי": ("גבאי", "ATT"),
    "חיים יגיל אוחנה": ("אוחנה", "ATT"),
    "יוסף אבו לבן": ("אבו לבן", "ATT"),
    "לוסיאלמו פאלנו סוארס": ("לוסיו", "ATT"),
    "מנזון ואדים": ("מנזון", "ATT"),
    "שלומי ארבייטמן": ("ארבייטמן", "ATT"),
    "תומאש פקהארט": ("פקהארט", "ATT"),
    "אמיר ח'לאילה": ("ח'לאילה", "ATT"),
    # GK (3-137 historical batch, 2008-2014 squad era)
    "אוהד כהן": ("אוהד כהן", "GK"),
    "אורי מכלוף": ("מכלוף", "GK"),
    "גליל בן שאנן": ("בן שאנן", "GK"),
    "דור דוידי": ("דוידי", "GK"),
    "דניאל ליפשיץ": ("ליפשיץ'", "GK"),
    "מרסין גרז'גורז' קאבץ'": ("קאבץ'", "GK"),
    "קאלה דרשלר": ("קאלה", "GK"),
    "שלומי בן חמו": ("בן חמו", "GK"),
    # DEF (3-137 historical batch)
    "אבי יחיאל": ("יחיאל", "DEF"),
    "איוון אלונסו גרידו פינזון": ("גרידו", "DEF"),
    "בוג'אן מרקוביץ'": ("מרקוביץ'", "DEF"),
    "בן אלגרבלי": ("אלגרבלי", "DEF"),
    "בן והבה": ("והבה", "DEF"),
    "דנילו מורירה": ("מורירה", "DEF"),
    "לואיס פיליפה בטיסטה טורס": ("טורס", "DEF"),
    "עודד גביש": ("גביש", "DEF"),
    "צפניה נדב כדר": ("כידר", "DEF"),
    "קלמי סבן": ("סבן", "DEF"),
    "ראין אלכסנדר אדליי": ("אדליי", "DEF"),
    "שי לוק": ("לוק", "DEF"),
    "שמעון הרוש": ("הרוש", "DEF"),
    "שמעון לוגסי": ("לוגסי", "DEF"),
    # MID (3-137 historical batch)
    "אבירם ברוכיאן": ("ברוכיאן", "MID"),
    "אור חביביאן": ("חביביאן", "MID"),
    "איברהים עבדול ראזק": ("עבדול רזאק", "MID"),
    "איל שן": ("שן", "MID"),
    "אמג'אד סלימאן": ("סלימאן", "MID"),
    "גיימס ביסו": ("ביסו", "MID"),
    "דוד רביבו": ("רביבו", "MID"),
    "דיויד הוברט": ("הובר", "MID"),
    "דנדי אוצ'ינה אוקוגו": ("אוקוגו", "MID"),
    "ויליאם נג'ובו": ("נג'ובו", "MID"),
    "יוסי שבחון": ("שבחון", "MID"),
    "יוסף אופיר": ("אופיר", "MID"),
    "יוסף טורזמן": ("יוסי תורג'מן", "MID"),
    "יחיאל צגאי הבטמו": ("צגאי", "MID"),
    "יצחק וקנין": ("וקנין", "MID"),
    "ירדן משה אבוחצירה": ("אבוחצירה", "MID"),
    "לוטם זינו": ("זינו", "MID"),
    "ליאור ג'אן": ("ג'אן", "MID"),
    "לריה קינגסטון": ("קינגסטון", "MID"),
    "מוחמד אדאמו": ("אדאמו", "MID"),
    "מזי פטריק אוקו אוסייקו": ("אוסייקו", "MID"),
    "מרדכי מלכה": ("מלכה", "MID"),
    "ניקולאס גסטון פלזוק": ("פלצ'וק", "MID"),
    "ננאד קיסו": ("קיסו", "MID"),
    "ערן לוי": ("לוי", "MID"),
    "פטר גרביץ'": ("גרביץ'", "MID"),
    "פיראס עווד": ("עווד", "MID"),
    "צח ברבי": ("ברבי", "MID"),
    "קובי דג'אני": ("דג'אני", "MID"),
    "רביד גזל": ("גזל", "MID"),
    "רועי קהת": ("קהת", "MID"),
    "ריקרדו ריביירו פרננדז": ("פרננדז", "MID"),
    # ATT (3-137 historical batch)
    "אוהד קדוסי": ("קדוסי", "ATT"),
    "בסיט אברהם": ("בסיט", "ATT"),
    "ברנרדו לינו דה קסטרו פאהס דה ואסקונקלוס": ("ואסקונקלוס", "ATT"),
    "ברק בדש": ("בדש", "ATT"),
    "גלינור אורביל פליט": ("פלט", "ATT"),
    "חנן פדידה": ("פדידה", "ATT"),
    "יונתן אוזן": ("אוזן", "ATT"),
    "ליאור אסולין": ("אסולין", "ATT"),
    "עידו אקסברד": ("אקסברד", "ATT"),
    "תומר סויסה": ("סויסה", "ATT"),
    # 3-137 historical batch, round 2 (subs revealed after their starter's own mapping unblocked them)
    "גל דהן": ("דהן", "DEF"),
    "דראשקו בוזוביץ'": ("בוזוביץ'", "DEF"),
    "גיל בלומשטיין": ("בלומשטיין", "MID"),
    "יוסי אלקיים": ("אלקיים", "MID"),
    "צחי מחלוף": ("מחלוף", "ATT"),
    # Follow-up addition (last remaining unmapped name blocking rows).
    # Site spelling is "איאד אבו עוביד" (Iyad Abu Ubaid) — a variant/typo
    # for the same player the user knows as Eitan Abu Abid; short display
    # name kept as the user specified.
    "איאד אבו עוביד": ("אבו עביד", "DEF"),
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
    # Older archived matches occasionally have fewer than 11 names in the
    # source page itself (a genuine gap in football.org.il's own data, not
    # a parsing failure) — accept whatever count is present rather than
    # blocking the whole match on it. The GK check stays strict since it's
    # a much stronger signal that the block was sliced correctly.
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
    # PlayerOut/PlayerIn divs carry a leading sr-only accessibility label
    # ("יצא"/"נכנס") before the actual name — strip it, or it gets glued
    # onto the name (e.g. "יצא רועי גורדנה") and silently fails to match
    # the starter's real name, dropping the substitution entirely.
    text = re.sub(r"<[^>]+>", "", raw).strip()
    text = re.sub(r"^(יצא|נכנס)\s*", "", text)
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


# football.org.il's own placeholder for a player it has no name on file for
# (confirmed by checking the player's profile page — it shows "*****" there
# too, so this isn't recoverable from any page on the site). Shown as-is
# rather than treated as an unmapped name requiring the user's input, since
# there's nothing to map it to. Position is genuinely unknowable too (the
# page doesn't encode per-player position anywhere), so these are collected
# separately rather than guessed into DEF/MID/ATT — they get appended as a
# trailing group instead. NOTE: if a single match has two or more anonymous
# outfield players who are BOTH subbed off, sub pairing for them may be
# wrong (subs_raw is keyed by raw name, and every anonymous starter shares
# the same raw name "*****") — accepted as a rare edge case given their
# identity is unknown either way.
UNKNOWN_PLAYER_RAW = "*****"
UNKNOWN_PLAYER_DISPLAY = "לא ידוע"


def build_lineup(starters, subs_raw):
    """
    starters: list of (raw_name, is_gk)
    subs_raw: {raw_out_name: raw_in_name}
    Returns the single-line, " / "-separated lineup string, or raises
    ParseError listing any unmapped names.
    """
    unmapped = set()
    groups = {pos: [] for pos in POSITION_ORDER}
    unknown_list = []
    gk_line = None

    def sub_in_display(sub_raw):
        # Returns the sub-in player's short name, or None if it's an
        # unmapped name that should block the whole match. The incoming
        # sub can itself be the site's anonymous-player placeholder.
        if sub_raw == UNKNOWN_PLAYER_RAW:
            return UNKNOWN_PLAYER_DISPLAY
        sub_mapped = map_name(sub_raw)
        if sub_mapped is None:
            unmapped.add(sub_raw)
            return None
        return sub_mapped[0]

    for raw_name, is_gk in starters:
        if raw_name == UNKNOWN_PLAYER_RAW:
            display = UNKNOWN_PLAYER_DISPLAY
            if raw_name in subs_raw:
                sub_short = sub_in_display(subs_raw[raw_name])
                if sub_short is not None:
                    display = f"{UNKNOWN_PLAYER_DISPLAY} ({sub_short})"
            if is_gk:
                gk_line = display
            else:
                unknown_list.append(display)
            continue

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
            sub_short = sub_in_display(subs_raw[raw_name])
            if sub_short is not None:
                display = f"{short} ({sub_short})"

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
    while lines and lines[-1] == "":
        lines.pop()
    if unknown_list:
        lines.append(", ".join(unknown_list))
    return " / ".join(lines)


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
