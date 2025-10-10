import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timezone
from urllib.parse import urljoin
import os

BASE_PAGE = "https://www.ruhabenjamin.com/events"
OUTPUT_FILE = "docs/ruha.ics"

def fetch_ics_links(page_url: str):
    resp = requests.get(page_url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []
    for a in soup.find_all("a"):
        text = (a.get_text(strip=True) or "").lower()
        # The page renders an explicit "ICS" link per event.
        # Example seen 2025-10-10: an <a> with visible text "ICS".
        if text == "ics":
            href = a.get("href")
            if href:
                links.append(urljoin(page_url, href))
    return links

def merge_ics_from_links(ics_urls):
    master = Calendar()
    seen_uids = set()
    now = datetime.now(timezone.utc)

    for url in ics_urls:
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            # Parse the individual ICS
            subcal = Calendar(r.text)

            for ev in subcal.events:
                # De-dup by UID if present
                uid = getattr(ev, "uid", None) or f"{ev.name}-{ev.begin}-{ev.location}"
                if uid in seen_uids:
                    continue

                # Keep only upcoming events (or ongoing). Comment out this block to keep all.
                try:
                    ev_end = ev.end if ev.end is not None else ev.begin
                    # If timezone-naive, treat as UTC for comparison (ics may already be tz-aware)
                    if isinstance(ev_end, datetime) and ev_end.tzinfo is None:
                        ev_end = ev_end.replace(tzinfo=timezone.utc)
                    if ev_end < now:
                        continue
                except Exception:
                    # If anything odd with dates, include conservatively
                    pass

                master.events.add(ev)
                seen_uids.add(uid)

        except Exception as e:
            print(f"⚠️ Skipping {url}: {e}")

    return master

def main():
    print(f"Fetching events page: {BASE_PAGE}")
    ics_links = fetch_ics_links(BASE_PAGE)
    print(f"Found {len(ics_links)} ICS links")

    calendar = merge_ics_from_links(ics_links)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(calendar.serialize())

    print(f"✅ Saved {len(calendar.events)} events to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
