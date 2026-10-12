"""Collect India funding / investor events into the Events tab, 3 times a day.

The workflow wakes up every 15 minutes between 8:30 AM and 7:15 PM IST. Each day
gets 3 random run times between 9 AM and 7 PM IST, 2 to 3 hours apart (the same
plan for the whole day, derived from the date). A wake-up collects only when a
planned time has passed and has not been covered yet; runs are logged in the
"Events Run Log" tab, so a delayed or skipped wake-up is caught up by the next one.

Env: GCP_SERVICE_ACCOUNT_KEY, SHEET_ID (optional), FORCE_RUN=true (manual run now),
DRY_RUN=true (print instead of writing).
"""
import os
import random
from datetime import datetime, timedelta

import requests

from event_sources import FETCHERS, IST
from events_sheet import get_tab, merge_events
from fetch_vc_news import HEADERS, setup_google_sheet

RUN_LOG_TAB = "Events Run Log"
RUN_LOG_HEADER = ["Run time (IST)", "Planned slot (IST)", "Candidates", "New events", "Updated events", "Notes"]

WINDOW_START, WINDOW_END = 9 * 60, 19 * 60  # minutes after midnight IST
MIN_GAP, MAX_GAP = 120, 180
LATEST_CATCH_UP = 19 * 60 + 30


def daily_plan(day):
    """Three run times (minutes after midnight IST) for `day`, 2-3 hours apart, within 9 AM-7 PM."""
    rng = random.Random(f"events-{day.isoformat()}")
    gaps = [rng.randint(MIN_GAP, MAX_GAP), rng.randint(MIN_GAP, MAX_GAP)]
    first = rng.randint(WINDOW_START, WINDOW_END - sum(gaps))
    return [first, first + gaps[0], first + gaps[0] + gaps[1]]


def fmt_minutes(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def due_slot(now, runs_today):
    """The planned slot this wake-up should cover, or None.

    runs_today: datetimes (IST) of collections already done today.
    """
    minutes = now.hour * 60 + now.minute
    if minutes > LATEST_CATCH_UP:
        return None
    passed = [slot for slot in daily_plan(now.date()) if slot <= minutes]
    if len(runs_today) >= len(passed):
        return None
    # Keep the 2-hour minimum after a late (caught-up) run
    if runs_today and now - max(runs_today) < timedelta(minutes=MIN_GAP):
        return None
    return passed[len(runs_today)]


def runs_logged_today(log_values, today):
    runs = []
    for row in log_values[1:]:
        try:
            when = datetime.strptime(row[0], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        except (ValueError, IndexError):
            continue
        # Manual runs don't use up a planned slot
        if when.date() == today and (row[1:2] or [""])[0] != "manual":
            runs.append(when)
    return runs


def collect(today):
    session = requests.Session()
    session.headers.update(HEADERS)
    events = []
    for name, fetcher in FETCHERS:
        try:
            found = fetcher(session, today)
        except Exception as e:
            print(f"[{name}] ERROR: {e}")
            continue
        print(f"[{name}] {len(found)} upcoming India investment events")
        events += found
    return events


def run():
    now = datetime.now(IST)
    force = os.environ.get("FORCE_RUN", "").lower() == "true"
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"
    spreadsheet = setup_google_sheet().spreadsheet

    log_tab, log_values = get_tab(spreadsheet, RUN_LOG_TAB, RUN_LOG_HEADER)
    plan = ", ".join(fmt_minutes(m) for m in daily_plan(now.date()))
    slot = due_slot(now, runs_logged_today(log_values, now.date()))
    if slot is None and not force:
        print(f"Not a run time. Today's plan (IST): {plan}; now {now:%H:%M}.")
        return
    slot_label = "manual" if slot is None else fmt_minutes(slot)
    print(f"Collecting events (slot {slot_label}; today's plan {plan}; now {now:%H:%M} IST)")

    events = collect(now.date())
    stamp = now.strftime("%Y-%m-%d %H:%M")
    counts, new_rows = merge_events(spreadsheet, events, stamp, dry_run=dry_run)
    print(f"Events: {len(events)} candidates -> {counts['new']} new, {counts['updated']} updated, "
          f"{counts['same']} unchanged")
    if dry_run:
        for row in new_rows[:40]:
            print("   ", " | ".join(cell.replace("\n", ", ")[:60] for cell in row[:6]))
        return
    log_tab.append_row([stamp, slot_label, len(events), counts["new"], counts["updated"],
                        "manual run" if slot is None else ""], value_input_option="RAW")


if __name__ == "__main__":
    run()
