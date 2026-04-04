import requests
import os
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from dateutil.parser import parse

load_dotenv()

REQUIRED_ENV_VARS = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
if missing:
    print(f"❌ Missing required env vars: {', '.join(missing)}")
    exit(1)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POSTED_GAMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posted_radio.txt")
TEAM_ID = int(os.getenv("TEAM_ID", "137"))
FORCE_POST = os.getenv("FORCE_POST", "false").lower() == "true"


def fetch_with_retry(url, retries=3, backoff=2, **kwargs):
    for attempt in range(retries):
        try:
            res = requests.get(url, **kwargs)
            if res.status_code == 200:
                return res
            print(f"⚠️ HTTP {res.status_code} for {url} (attempt {attempt + 1})")
        except Exception as e:
            print(f"⚠️ Request error: {e} (attempt {attempt + 1})")
        if attempt < retries - 1:
            time.sleep(backoff)
    return None


def is_archive_ready(game_start_utc):
    """Returns True if 4.5 hours have passed since game start (proxy for archive availability)."""
    return datetime.now(timezone.utc) > game_start_utc + timedelta(hours=4, minutes=30)


def get_recent_gamepks(team_id=137):
    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = (now_utc + timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={team_id}&startDate={start_date}&endDate={end_date}"
    res = fetch_with_retry(url, timeout=10)
    if res is None:
        print("❌ Could not fetch MLB schedule")
        return []
    data = res.json()
    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry["games"]:
            if game["status"]["detailedState"] in ("Final", "Completed Early"):
                game_start_utc = parse(game["gameDate"])  # dateutil handles the Z suffix → timezone-aware UTC
                official_date = date_entry["date"].replace("-", "")
                games.append((
                    game_start_utc,
                    game["gamePk"],
                    game["teams"]["away"]["team"]["name"],
                    game["teams"]["home"]["team"]["name"],
                    official_date,
                ))
    games.sort(reverse=True)
    return [(pk, away, home, d, start) for start, pk, away, home, d in games]


def already_posted(gamepk, path=None):
    if path is None:
        path = POSTED_GAMES_FILE
    if not os.path.exists(path):
        return False
    with open(path, "r") as f:
        return str(gamepk) in f.read().splitlines()


def mark_as_posted(gamepk, path=None):
    if path is None:
        path = POSTED_GAMES_FILE
    with open(path, "a") as f:
        f.write(f"{gamepk}\n")


def send_telegram_message(gamepk, away, home, date=""):
    web_url = f"https://golazosteve.github.io/SFGRadioArchived/watch/?g={gamepk}&d={date}"
    message = f"📻 {away} @ {home}"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "Listen", "url": web_url}]
            ]
        },
    }
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10,
        )
        return res.ok
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")
        return False


def main():
    print("📻 Radio Archive Bot")
    if FORCE_POST:
        print("⚡ FORCE_POST mode enabled — skipping already-posted check")

    games = get_recent_gamepks(team_id=TEAM_ID)
    print(f"🧾 Found {len(games)} recent final games")

    for gamepk, away, home, date, game_start in games:
        print(f"🔍 Checking gamePk: {gamepk} ({away} @ {home})")

        if not FORCE_POST and already_posted(gamepk):
            print("⏩ Already posted")
            continue

        if not FORCE_POST and not is_archive_ready(game_start):
            print(f"⏳ Archive not ready yet (game started {game_start})")
            continue

        if send_telegram_message(gamepk, away, home, date):
            mark_as_posted(gamepk)
            print(f"✅ Posted radio link for {gamepk}")
        else:
            print(f"⚠️ Failed to post for {gamepk}")
        break


if __name__ == "__main__":
    main()
