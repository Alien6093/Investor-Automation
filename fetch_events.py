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
import re
import time
from collections import Counter
import traceback
from datetime import datetime

import requests

from event_sources import FETCHERS, IST, set_deadline
from events_sheet import get_tab, merge_events
from fetch_vc_news import HEADERS, setup_google_sheet
from lark_notify import SHOWN, link, md, notify, plural, short

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
    set_deadline(deadline)  # every request stops once the time is up, not just between sources
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

    # The log row is written first ("running") and completed at the end, so a run that GitHub
    # stops part-way still shows up (and still counts as today's run for the fallback)
    log_row = None
    if not dry_run:
        response = log_tab.append_row([now.strftime("%Y-%m-%d %H:%M"), label[:100], "", "", "", "running…"],
                                      value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1")
        match = re.search(r"![A-Z]+(\d+)", (response or {}).get("updates", {}).get("updatedRange", ""))
        log_row = int(match.group(1)) if match else None

    events, notes, counts, new_rows = [], [], None, []
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
            notify_lark(spreadsheet.url, label, events, counts, new_rows, notes)
            row = [now.strftime("%Y-%m-%d %H:%M"), label[:100], len(events), counts["new"] if counts else "",
                   counts["updated"] if counts else "", "; ".join(notes)[:500] or "done"]
            if log_row:
                log_tab.update([row], f"A{log_row}:F{log_row}", value_input_option="RAW")
            else:
                log_tab.append_row(row, value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1")


def notify_lark(sheet_url, label, events, counts, new_rows, notes):
    """Summary to the Lark group once the Events tab is updated (or the run failed)."""
    by_source = Counter(event["source"].split(" - ")[0] for event in events)
    blocks = [
        (f"**{plural(counts['new'], 'new event')}** added to the Events tab"
         f" ({plural(counts['updated'], 'event')} seen again)" if counts else "**Nothing was saved** (see problems)")
        + f"\nStarted by: {md(label)}",
    ]
    if by_source:
        blocks.append("**By source**\n" + "\n".join(f"{md(source)}: {n} upcoming India events" for source, n in by_source.most_common()))
    if new_rows:
        lines = [f"• {link(short(row[0], 80), row[4] or row[6].split(chr(10))[0])} — {md(row[1])}"
                 f"{' · ' + md(row[2]) if row[2] else ''} ({md(row[5])})" for row in new_rows[:SHOWN]]
        more = f"\n…and {len(new_rows) - SHOWN} more in the sheet" if len(new_rows) > SHOWN else ""
        blocks += ["---", "**New events**\n" + "\n".join(lines) + more]
    if notes:
        blocks += ["---", "**⚠ Problems**\n" + "\n".join(f"• {short(note, 160)}" for note in notes[:8])]
    blocks += ["---", link("Open the sheet", sheet_url)]
    notify("Events (GitHub) · run finished" if counts else "Events (GitHub) · run failed", blocks,
           warning=bool(notes) or not counts)


if __name__ == "__main__":
    run()
