import time
import os
import json
import requests
from html import escape
from datetime import datetime, timezone, timedelta
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ── CONFIG ──────────────────────────────────────────────────────────────
FD_API_KEY      = os.getenv("FD_API_KEY")
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL", "").rstrip("/")
CONFLUENCE_EMAIL = os.getenv("CONFLUENCE_EMAIL")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")
CONFLUENCE_PAGE_ID = os.getenv("CONFLUENCE_PAGE_ID")
CONFLUENCE_PAGE_TITLE = os.getenv("CONFLUENCE_PAGE_TITLE", "World Cup 2026 Sweepstake")
RUN_ONCE = os.getenv("RUN_ONCE", "false").lower() in {"1", "true", "yes", "on"}
COMPETITION     = "WC"

BST = pytz.timezone("Europe/London")
CHECK_DELAY_HOURS = 2   # hours after kick-off to check result
POLL_INTERVAL_SECS = 60 # while actively polling during a match window

# ── LOGIC ────────────────────────────────────────────────────────────────
def fetch_standings():
    if not FD_API_KEY:
        raise ValueError("FD_API_KEY not set")
    url = f"https://api.football-data.org/v4/competitions/{COMPETITION}/standings"
    r = requests.get(url, headers={"X-Auth-Token": FD_API_KEY})
    r.raise_for_status()
    return r.json().get("standings", [])

def fetch_matches():
    if not FD_API_KEY:
        raise ValueError("FD_API_KEY not set")
    url = f"https://api.football-data.org/v4/competitions/{COMPETITION}/matches"
    r = requests.get(url, headers={"X-Auth-Token": FD_API_KEY})
    r.raise_for_status()
    return r.json().get("matches", [])

def get_next_check_time():
    """
    Returns the next datetime (UTC) at which we should wake up and check.
    That's 2 hours after the next upcoming finished or scheduled fixture.
    """
    try:
        matches = fetch_matches()
    except Exception as e:
        print(f"  ⚠️ Error fetching matches: {e}")
        # If we can't get matches, try again in 1 hour
        return datetime.now(timezone.utc) + timedelta(hours=1)

    now_utc = datetime.now(timezone.utc)
    upcoming_checks = []

    # fetch_matches returns a list directly or a dict with a "matches" key
    match_list = matches.get("matches", []) if isinstance(matches, dict) else matches

    for m in match_list:
        # utcDate is in format "2026-06-11T20:00:00Z"
        kickoff_utc = datetime.strptime(m["utcDate"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        check_time = kickoff_utc + timedelta(hours=CHECK_DELAY_HOURS)
        
        # We only care about checks that haven't happened yet or happened very recently (within 1h)
        # to ensure we don't skip a result if the bot just started up.
        if check_time > now_utc - timedelta(hours=1):
            upcoming_checks.append(check_time)
    
    return min(upcoming_checks) if upcoming_checks else None

def sleep_until(target_dt):
    """Sleep until a specific datetime, printing a countdown."""
    now = datetime.now(timezone.utc)
    delta = (target_dt - now).total_seconds()
    if delta <= 0:
        return
    
    target_bst = target_dt.astimezone(BST)
    print(f"  💤 Sleeping until {target_bst.strftime('%Y-%m-%d %H:%M BST')} "
          f"({delta/3600:.1f}h from now)")
    time.sleep(max(delta, 0))

# ── SWEEPSTAKE ASSIGNMENTS ───────────────────────────────────────────────
ASSIGNMENTS = {
    "Max":      ["Brazil", "Iraq", "Jordan"],
    "Yifan":    ["Canada", "Bosnia and Herzegovina", "Netherlands"],
    "Archie L": ["Tunisia", "Sweden", "South Africa"],
    "Linus":    ["Uzbekistan", "DR Congo", "Egypt"],
    "Gwennan":  ["Saudi Arabia", "Uruguay", "Germany"],
    "Archie F": ["Austria", "Scotland", "Ivory Coast"],
    "Nick B":   ["Portugal", "Colombia", "Croatia"],
    "Iain":     ["Switzerland", "Czech Republic", "Panama"],
    "Laura":    ["Japan", "Argentina", "England"],
    "Gareth":   ["Curaçao", "Haiti", "Senegal"],
    "Linus (2)":["Norway", "Cape Verde", "New Zealand"],
    "Raph":     ["Morocco", "USA", "South Korea"],
    "Linus (3)":["Ghana", "Iran", "Spain"],
    "Marc":     ["Mexico", "France", "Qatar"],
    "Irene":    ["Australia", "Ecuador", "Belgium"],
    "Katie":    ["Algeria", "Paraguay", "Turkey"],
}

STATUS_ICONS = {
    "in":     "🟢",
    "out":    "❌",
    "last":   "🥄",
    "second": "🥈",
    "winner": "🥇",
}

TEAM_FLAGS = {
    "Brazil": ":flag_br:", "Argentina": ":flag_ar:", "England": ":england:",
    "France": ":flag_fr:", "Spain": ":flag_es:", "Germany": ":flag_de:",
    "Portugal": ":flag_pt:", "Netherlands": ":flag_nl:", "Belgium": ":flag_be:",
    "Croatia": ":flag_hr:", "Morocco": ":flag_ma:", "Japan": ":flag_jp:",
    "USA": ":flag_us:", "Mexico": ":flag_mx:", "Australia": ":flag_au:",
    "Switzerland": ":flag_ch:", "Colombia": ":flag_co:", "Uruguay": ":flag_uy:",
    "Senegal": ":flag_sn:", "Egypt": ":flag_eg:", "Saudi Arabia": ":flag_sa:",
    "Iran": ":flag_ir:", "South Korea": ":flag_kr:", "Ghana": ":flag_gh:",
    "Canada": ":flag_ca:", "Ecuador": ":flag_ec:", "Qatar": ":flag_qa:",
    "Tunisia": ":flag_tn:", "Norway": ":flag_no:", "Scotland": ":scotland:",
    "Turkey": ":flag_tr:", "Algeria": ":flag_dz:", "Paraguay": ":flag_py:",
    "Austria": ":flag_at:", "Ivory Coast": ":flag_ci:", "Panama": ":flag_pa:",
    "Czech Republic": ":flag_cz:", "New Zealand": ":flag_nz:", "Sweden": ":flag_se:",
    "Iraq": ":flag_iq:", "Jordan": ":flag_jo:", "Haiti": ":flag_ht:",
    "DR Congo": ":flag_cd:", "Uzbekistan": ":flag_uz:", "Cape Verde": ":flag_cv:",
    "Bosnia and Herzegovina": ":flag_ba:", "Curaçao": ":flag_cw:",
    "South Africa": ":flag_za:",
}

TEAM_FLAG_ALIASES = {
    "Cote d'Ivoire": "Ivory Coast",
    "Côte d'Ivoire": "Ivory Coast",
    "Côte d’Ivoire": "Ivory Coast",
    "Curacao": "Curaçao",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "United States": "USA",
    "United States of America": "USA",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Democratic Republic of the Congo": "DR Congo",
}


def get_team_flag(team_name):
    canonical_name = TEAM_FLAG_ALIASES.get(team_name, team_name)
    return TEAM_FLAGS.get(canonical_name, team_name)


def get_team_emoji(team_name):
    flag = get_team_flag(team_name)
    if flag.startswith(":") and flag.endswith(":"):
        return flag.strip(":")
    return flag


def format_team_cell(team_name):
    marker = get_team_flag(team_name)
    return f"{marker} {escape(team_name)}"


def adf_text(text, marks=None):
    node = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def adf_emoji(team_name):
    flag = get_team_flag(team_name)
    if flag.startswith(":") and flag.endswith(":"):
        return {
            "type": "emoji",
            "attrs": {
                "shortName": flag,
                "text": flag,
            },
        }

    return adf_text(flag)


def adf_paragraph(content):
    return {"type": "paragraph", "content": content}


def build_confluence_adf_document(team_statuses):
    updated = datetime.now(BST).strftime("%d %b %Y %H:%M BST")

    rows = [
        {
            "type": "tableRow",
            "content": [
                {"type": "tableHeader", "content": [adf_paragraph([adf_text("Name")])]},
                {"type": "tableHeader", "content": [adf_paragraph([adf_text("Teams")])]},
                {"type": "tableHeader", "content": [adf_paragraph([adf_text("Status")])]},
            ],
        }
    ]

    for person, teams in ASSIGNMENTS.items():
        team_cells = [adf_paragraph([adf_emoji(team), adf_text(f" {team}")]) for team in teams]
        status_cells = [
            adf_paragraph([adf_text(STATUS_ICONS.get(team_statuses.get(team, "in"), "🟢"))])
            for team in teams
        ]

        rows.append(
            {
                "type": "tableRow",
                "content": [
                    {"type": "tableCell", "content": [adf_paragraph([adf_text(person)])]},
                    {"type": "tableCell", "content": team_cells},
                    {"type": "tableCell", "content": status_cells},
                ],
            }
        )

    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "heading", "attrs": {"level": 1}, "content": [adf_text(CONFLUENCE_PAGE_TITLE)]},
            {"type": "heading", "attrs": {"level": 2}, "content": [adf_text("Prizes")]},
            {
                "type": "bulletList",
                "content": [
                    {"type": "listItem", "content": [adf_paragraph([adf_text("1st place - £50")])]},
                    {"type": "listItem", "content": [adf_paragraph([adf_text("2nd place - £20")])]},
                    {"type": "listItem", "content": [adf_paragraph([adf_text("Last place - £10")])]},
                ],
            },
            adf_paragraph([adf_text("Last place decided by: points -> goal diff -> goals scored (all ascending). Coinflip if tied.", marks=[{"type": "em"}])]),
            {"type": "table", "content": rows},
            adf_paragraph([adf_text("Legend: "), adf_text("🟢 Still in | ❌ Out | 🥄 Last place | 🥈 Runner-up | 🥇 Winner")]),
            adf_paragraph([adf_text(f"Updated: {updated}", marks=[{"type": "em"}])]),
        ],
    }

# ── LOGIC ────────────────────────────────────────────────────────────────
def compute_team_statuses(standings, matches):
    statuses = {}
    all_team_stats = {}

    stage_order = {
        "GROUP_STAGE": 0, "ROUND_OF_32": 1, "ROUND_OF_16": 2,
        "QUARTER_FINALS": 3, "SEMI_FINALS": 4, "THIRD_PLACE": 5,
        "FINAL": 6
    }

    # ── GROUP STAGE ──────────────────────────────────────────────────────
    for group in standings:
        if group["type"] != "TOTAL":
            continue
        table = group["table"]
        group_teams = [row["team"]["name"] for row in table]

        remaining = {t: 0 for t in group_teams}
        for m in matches:
            if m["stage"] != "GROUP_STAGE" or m["status"] == "FINISHED":
                continue
            h, a = m["homeTeam"]["name"], m["awayTeam"]["name"]
            if h in remaining: remaining[h] += 1
            if a in remaining: remaining[a] += 1

        for row in table:
            name = row["team"]["name"]
            pts  = row["points"]
            gd   = row["goalDifference"]
            gf   = row["goalsFor"]

            all_team_stats[name] = {
                "pts": pts, "gd": gd, "gf": gf,
                "stage_reached": "GROUP_STAGE"
            }

            max_pts = pts + remaining[name] * 3
            insurmountable = sum(
                1 for r in table
                if r["team"]["name"] != name and r["points"] > max_pts
            )
            statuses[name] = "out" if insurmountable >= 2 else "in"

    # ── KNOCKOUT STAGE ───────────────────────────────────────────────────
    knockout_stages = [
        "ROUND_OF_32", "ROUND_OF_16", "QUARTER_FINALS",
        "SEMI_FINALS", "THIRD_PLACE", "FINAL"
    ]
    for m in sorted(matches, key=lambda x: stage_order.get(x["stage"], -1)):
        if m["stage"] not in knockout_stages or m["status"] != "FINISHED":
            continue

        home  = m["homeTeam"]["name"]
        away  = m["awayTeam"]["name"]
        winner_side = m.get("score", {}).get("winner")

        for name in [home, away]:
            if name not in all_team_stats:
                all_team_stats[name] = {"pts": 0, "gd": 0, "gf": 0}
            all_team_stats[name]["stage_reached"] = m["stage"]

        if winner_side == "HOME_TEAM":
            winner, loser = home, away
        elif winner_side == "AWAY_TEAM":
            winner, loser = away, home
        else:
            continue

        if m["stage"] == "FINAL":
            statuses[winner] = "winner"
            statuses[loser]  = "second"
        elif m["stage"] == "THIRD_PLACE":
            pass  # handled by FINAL winner/runner-up above
        else:
            statuses[loser] = "out"

    # ── LAST PLACE ───────────────────────────────────────────────────────
    eliminated = [
        (name, stats) for name, stats in all_team_stats.items()
        if statuses.get(name) == "out"
    ]
    if eliminated:
        worst = sorted(
            eliminated,
            key=lambda x: (
                stage_order.get(x[1].get("stage_reached", "GROUP_STAGE"), 0),
                x[1]["pts"],
                x[1]["gd"],
                x[1]["gf"],
            )
        )[0][0]
        statuses[worst] = "last"

    return statuses

def build_confluence_storage_message(team_statuses):
    return json.dumps(build_confluence_adf_document(team_statuses))


def confluence_api_base():
    if not CONFLUENCE_BASE_URL:
        raise ValueError("CONFLUENCE_BASE_URL not set")
    return f"{CONFLUENCE_BASE_URL}/api/v2"


def confluence_auth():
    if not CONFLUENCE_EMAIL:
        raise ValueError("CONFLUENCE_EMAIL not set")
    if not CONFLUENCE_API_TOKEN:
        raise ValueError("CONFLUENCE_API_TOKEN not set")
    return (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)


def fetch_confluence_page(page_id):
    url = f"{confluence_api_base()}/pages/{page_id}"
    resp = requests.get(url, auth=confluence_auth(), headers={"Accept": "application/json"})
    resp.raise_for_status()
    return resp.json()


def update_confluence_page(content):
    if not CONFLUENCE_PAGE_ID:
        raise ValueError("CONFLUENCE_PAGE_ID not set")

    page = fetch_confluence_page(CONFLUENCE_PAGE_ID)
    version = page["version"]["number"] + 1
    title = page.get("title") or CONFLUENCE_PAGE_TITLE

    payload = {
        "id": CONFLUENCE_PAGE_ID,
        "status": "current",
        "title": title,
        "version": {"number": version},
        "body": {
            "representation": "atlas_doc_format",
            "value": content,
        },
    }

    url = f"{confluence_api_base()}/pages/{CONFLUENCE_PAGE_ID}"
    resp = requests.put(
        url,
        auth=confluence_auth(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json=payload,
    )
    resp.raise_for_status()
    print(f"  ✅ Confluence page updated successfully: {title} (v{version})")


def run_one_update():
    standings = fetch_standings()
    matches = fetch_matches()
    statuses = compute_team_statuses(standings, matches)
    print("  📊 Running one-shot Confluence update...")
    text = build_confluence_storage_message(statuses)
    update_confluence_page(text)
    return statuses

# ── MAIN LOOP ─────────────────────────────────────────────────────────────
def main():
    if not all([FD_API_KEY, CONFLUENCE_BASE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN, CONFLUENCE_PAGE_ID]):
        print("❌ Error: Missing Confluence or API environment variables. Please check your .env file.")
        print(f"FD_API_KEY: {'set' if FD_API_KEY else 'MISSING'}")
        print(f"CONFLUENCE_BASE_URL: {'set' if CONFLUENCE_BASE_URL else 'MISSING'}")
        print(f"CONFLUENCE_EMAIL: {'set' if CONFLUENCE_EMAIL else 'MISSING'}")
        print(f"CONFLUENCE_API_TOKEN: {'set' if CONFLUENCE_API_TOKEN else 'MISSING'}")
        print(f"CONFLUENCE_PAGE_ID: {'set' if CONFLUENCE_PAGE_ID else 'MISSING'}")
        return

    print("🏆 Sweepstake bot started in Confluence mode!")
    last_statuses = {}

    if RUN_ONCE:
        run_one_update()
        print("One-shot update complete; exiting.")
        return

    while True:
        next_check = get_next_check_time()

        if next_check is None:
            print("No upcoming fixtures — tournament may be over. Exiting.")
            break

        # Sleep until 2h after next kick-off
        sleep_until(next_check)

        # Once awake, poll every 60s for up to 60 mins
        # (handles matches that run into extra time)
        print(f"\n⚽ Checking results at {datetime.now(BST).strftime('%H:%M BST')}...")
        for attempt in range(60):
            try:
                standings = fetch_standings()
                matches   = fetch_matches()
                statuses  = compute_team_statuses(standings, matches)

                if statuses != last_statuses:
                    print(f"  📊 Status change on attempt {attempt+1} — updating Confluence...")
                    text = build_confluence_storage_message(statuses)
                    update_confluence_page(text)
                    last_statuses = statuses.copy()
                    break  # Got a clean update, go back to sleep
                else:
                    print(f"  ⏳ No change yet (attempt {attempt+1}/30), retrying in 60s...")
                    time.sleep(POLL_INTERVAL_SECS)

            except Exception as e:
                print(f"  ⚠️ Error: {e} — retrying in 60s")
                time.sleep(POLL_INTERVAL_SECS)

if __name__ == "__main__":
    main()