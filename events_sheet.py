"""The Events tab: one row per event, merged across every place it was seen.

Two sightings are the same event when they share an event-specific link (registration or
event page, not an organiser page / linktr.ee / short link) with a matching date, or when
the event name (ignoring case, spaces and punctuation) and the event date match. A later
sighting adds its source / links / author to the existing row and fills cells that were
still empty. The Chrome extension (master-extension, lib/sheets.js) writes the same tab
with the same rules.
"""
import gspread

from event_rules import is_event_specific_link, link_key, name_key

EVENTS_TAB = "Events"
EVENTS_HEADER = [
    "Event name", "Event date", "City / Online", "Organizer", "Registration link",
    "Sources", "Links", "Author profile URLs", "First added", "Last seen",
]
(NAME, DATE, CITY, ORGANIZER, REG_LINK, SOURCES, LINKS, AUTHORS, FIRST_ADDED, LAST_SEEN) = range(len(EVENTS_HEADER))
SEP = "\n"  # multi-value cells hold one value per line
MAX_VALUES = 40  # keep multi-value cells readable (and far below the 50,000-character cell limit)


class HeaderError(Exception):
    pass


def get_tab(spreadsheet, name, header, older_headers=()):
    """(worksheet, values). Writes the header into a new or empty tab (or over an older
    version of it). Refuses to go on when row 1 is something else: rows are written by
    position, so a missing / moved header would put values into the wrong rows."""
    try:
        tab = spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        tab = spreadsheet.add_worksheet(title=name, rows=200, cols=len(header))
    values = tab.get_all_values()
    first = values[0] if values else []
    if not any(cell.strip() for cell in first) or any(first[:len(old)] == list(old) for old in older_headers):
        tab.update([header], "A1")
        tab.freeze(rows=1)
        values = [header] + values[1:]
    elif first[:len(header)] != header:
        raise HeaderError(f'Row 1 of the "{name}" tab is not the expected header ({", ".join(header[:3])}, ...); '
                          "nothing was written to it")
    return tab, values


def _add_value(row, col, value):
    if not value:
        return False
    values = [v for v in row[col].split(SEP) if v]
    if value in values or len(values) >= MAX_VALUES:
        return False
    row[col] = SEP.join(values + [value])
    return True


class EventIndex:
    def __init__(self, rows):
        self.rows = rows  # sheet rows without the header, padded to the header width
        self.by_link, self.by_name_date = {}, {}
        for i in range(len(rows)):
            self._index(i)

    def _index(self, i):
        row = self.rows[i]
        for link in [row[REG_LINK]] + row[LINKS].split(SEP):
            key = link_key(link)
            if key and is_event_specific_link(link):
                self.by_link.setdefault(key, i)
        if name_key(row[NAME]) and row[DATE]:
            self.by_name_date.setdefault((name_key(row[NAME]), row[DATE]), i)

    def find(self, event):
        for link in [event.get("reg_link"), event.get("link")] + list(event.get("extra_links") or []):
            if not link or not is_event_specific_link(link):
                continue
            i = self.by_link.get(link_key(link))
            if i is not None and (not self.rows[i][DATE] or not event["date"] or self.rows[i][DATE] == event["date"]):
                return i
        return self.by_name_date.get((name_key(event["name"]), event["date"]))

    def merge(self, event, now):
        """Returns ('new' | 'updated' | 'same', row index)."""
        i = self.find(event)
        if i is None:
            row = [""] * len(EVENTS_HEADER)
            row[NAME], row[DATE] = event["name"][:250], event["date"]
            row[FIRST_ADDED] = now
            self.rows.append(row)
            i = len(self.rows) - 1
            status = "new"
        else:
            row, status = self.rows[i], "same"
        changed = False
        for col, key in ((CITY, "city"), (ORGANIZER, "organizer"), (REG_LINK, "reg_link")):
            if not row[col] and event.get(key):
                row[col] = event[key]
                changed = True
        changed |= _add_value(row, SOURCES, event.get("source"))
        for link in [event.get("link")] + list(event.get("extra_links") or []):
            changed |= _add_value(row, LINKS, link)
        changed |= _add_value(row, AUTHORS, event.get("author"))
        row[LAST_SEEN] = now
        if status == "same" and changed:
            status = "updated"
        self._index(i)
        return status, i


def _rows(values):
    return [(row + [""] * len(EVENTS_HEADER))[:len(EVENTS_HEADER)] for row in values[1:]]


def merge_events(spreadsheet, events, now, dry_run=False):
    if dry_run:
        try:
            values = spreadsheet.worksheet(EVENTS_TAB).get_all_values()
        except gspread.exceptions.WorksheetNotFound:
            values = [EVENTS_HEADER]
        index = EventIndex(_rows(values))
        original = len(index.rows)
        counts = {"new": 0, "updated": 0, "same": 0}
        for event in events:
            counts[index.merge(event, now)[0]] += 1
        return counts, index.rows[original:]

    for _ in range(3):
        tab, values = get_tab(spreadsheet, EVENTS_TAB, EVENTS_HEADER)
        existing = _rows(values)
        snapshot = [list(row) for row in existing]
        original = len(existing)
        index = EventIndex(existing)
        touched, counts = set(), {"new": 0, "updated": 0, "same": 0}
        for event in events:
            status, i = index.merge(event, now)
            counts[status] += 1
            if i < original:
                touched.add(i)  # Last seen changes even when nothing else does
        # Rows are updated by position: if another writer (the extension, or a person sorting /
        # deleting rows) changed those rows since they were read, merge again on a fresh copy
        check = _rows(tab.get_all_values())
        # Rows appended by another writer meanwhile are merged on the next attempt (no duplicates)
        if len(check) != original or any(check[i] != snapshot[i] for i in touched):
            continue
        updates = [{"range": f"A{i + 2}:J{i + 2}", "values": [index.rows[i]]} for i in sorted(touched)]
        if updates:
            tab.batch_update(updates)
        new_rows = index.rows[original:]
        if new_rows:
            tab.append_rows(new_rows, value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1")
        return counts, new_rows
    raise RuntimeError(f'The "{EVENTS_TAB}" tab kept changing while saving')
