"""Collect India funding / investor events into the Events tab.

Runs are started by the Chrome extension (master-extension): each of its full runs (3 a day
at random times between 9 AM and 7 PM IST) starts this workflow through GitHub's
workflow_dispatch, so both collect at the same times. GitHub's own schedule starts this
repo's jobs hours late, so it is only a fallback: once a day, it collects if no run was
logged today (laptop off all day). Every run is logged in the "Events Run Log" tab.

Env: GCP_SERVICE_ACCOUNT_KEY, SHEET_ID (optional), GITHUB_EVENT_NAME (set by Actions),
RUN_REASON (who started it), DRY_RUN=true (print instead of writing).
"""
import os
import time
import traceback
from datetime import datetime

import requests

from event_sources import FETCHERS, IST
from events_sheet import get_tab, merge_events
from fetch_vc_news import HEADERS, setup_google_sheet

RUN_LOG_TAB = "Events Run Log"
RUN_LOG_HEADER = ["Run time (IST)", "Started by", "Candidates", "New events", "Updated events", "Notes"]
OLD_RUN_LOG_HEADER = ["Run time (IST)", "Planned slot (IST)", "Candidates", "New events", "Updated events", "Notes"]

# Sources still waiting when a run reaches this many minutes are skipped (and logged), so a
# slow site can't use up the job's whole time and lose everything found so far
COLLECT_BUDGET_MINUTES = 30


def runs_logged_today(log_values, today):
    runs = []
    for row in log_values[1:]:
        try:
            when = datetime.strptime(row[0], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        except (ValueError, IndexError):
            continue
        if when.date() == today:
            runs.append(when)
    return runs


def collect(today, budget_minutes=COLLECT_BUDGET_MINUTES):
    """(events, notes): every source's upcoming India investment events."""
    session = requests.Session()
    session.headers.update(HEADERS)
    deadline = time.monotonic() + budget_minutes * 60
    events, notes = [], []
    for name, fetcher in FETCHERS:
        if time.monotonic() > deadline:
            notes.append(f"{name} skipped (time limit)")
            print(f"[{name}] skipped: the run reached its {budget_minutes}-minute collection limit")
            continue
        try:
            found = fetcher(session, today)
        except Exception as e:
            notes.append(f"{name} failed: {e.__class__.__name__}")
            print(f"[{name}] ERROR: {e}")
            continue
        print(f"[{name}] {len(found)} upcoming India investment events")
        events += found
    return events, notes


def run():
    now = datetime.now(IST)
    started_by = os.environ.get("GITHUB_EVENT_NAME", "") or "manual"
    reason = (os.environ.get("RUN_REASON") or "").strip()
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"
    spreadsheet = setup_google_sheet().spreadsheet

    log_tab, log_values = get_tab(spreadsheet, RUN_LOG_TAB, RUN_LOG_HEADER, older_headers=[OLD_RUN_LOG_HEADER])
    if started_by == "schedule":
        if runs_logged_today(log_values, now.date()):
            print(f"Fallback skipped: the extension already started a run today ({now:%Y-%m-%d} IST).")
            return
        label = "daily fallback (no run from the extension today)"
    else:
        label = reason or started_by
    print(f"Collecting events ({label}; {now:%Y-%m-%d %H:%M} IST)")

    events, notes, counts = [], [], None
    try:
        events, notes = collect(now.date())
        stamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M")
        counts, new_rows = merge_events(spreadsheet, events, stamp, dry_run=dry_run)
        print(f"Events: {len(events)} candidates -> {counts['new']} new, {counts['updated']} updated, "
              f"{counts['same']} unchanged")
        if dry_run:
            for row in new_rows[:40]:
                print("   ", " | ".join(cell.replace("\n", ", ")[:60] for cell in row[:6]))
    except Exception as e:
        notes.append(f"failed: {e}"[:300])
        traceback.print_exc()
        raise
    finally:
        if not dry_run:
            log_tab.append_row(
                [now.strftime("%Y-%m-%d %H:%M"), label[:100], len(events), counts["new"] if counts else "",
                 counts["updated"] if counts else "", "; ".join(notes)[:500]],
                value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1",
            )


if __name__ == "__main__":
    run()
