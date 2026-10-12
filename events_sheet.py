"""The Events tab: one row per event, merged across every place it was seen.

Two sightings are the same event when they share the registration link, or when
the event name (ignoring case, spaces and punctuation) and the event date match.
A later sighting adds its source / link / author to the existing row and fills
cells that were still empty.
"""
import gspread

from event_rules import link_key, name_key

EVENTS_TAB = "Events"
EVENTS_HEADER = [
    "Event name", "Event date", "City / Online", "Organizer", "Registration link",
    "Sources", "Links", "Author profile URLs", "First added", "Last seen",
]
(NAME, DATE, CITY, ORGANIZER, REG_LINK, SOURCES, LINKS, AUTHORS, FIRST_ADDED, LAST_SEEN) = range(len(EVENTS_HEADER))
SEP = "\n"  # multi-value cells hold one value per line


def get_tab(spreadsheet, name, header):
    try:
        tab = spreadsheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        tab = spreadsheet.add_worksheet(title=name, rows=200, cols=len(header))
    values = tab.get_all_values()
    if not values or values[0][:len(header)] != header:
        tab.update([header], "A1")
        tab.freeze(rows=1)
        values = [header] + (values[1:] if values and values[0][:1] == header[:1] else values)
    return tab, values


def _add_value(row, col, value):
    if not value:
        return False
    values = [v for v in row[col].split(SEP) if v]
    if value in values:
        return False
    row[col] = SEP.join(values + [value])
    return True


class EventIndex:
    def __init__(self, rows):
        self.rows = rows  # sheet rows without the header, padded to the header width
        self.by_link, self.by_name_date = {}, {}
        for i, row in enumerate(rows):
            self._index(i)

    def _index(self, i):
        row = self.rows[i]
        for link in [row[REG_LINK]] + row[LINKS].split(SEP):
            if link_key(link):
                self.by_link.setdefault(link_key(link), i)
        if name_key(row[NAME]) and row[DATE]:
            self.by_name_date.setdefault((name_key(row[NAME]), row[DATE]), i)

    def find(self, event):
        for link in (event.get("reg_link"), event.get("link")):
            if link_key(link) in self.by_link:
                return self.by_link[link_key(link)]
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
        changed |= _add_value(row, LINKS, event.get("link"))
        changed |= _add_value(row, AUTHORS, event.get("author"))
        row[LAST_SEEN] = now
        if status == "same" and changed:
            status = "updated"
        self._index(i)
        return status, i


def merge_events(spreadsheet, events, now, dry_run=False):
    tab, values = get_tab(spreadsheet, EVENTS_TAB, EVENTS_HEADER) if not dry_run else (None, None)
    if dry_run:
        try:
            values = spreadsheet.worksheet(EVENTS_TAB).get_all_values()
        except gspread.exceptions.WorksheetNotFound:
            values = [EVENTS_HEADER]
    existing = [(row + [""] * len(EVENTS_HEADER))[:len(EVENTS_HEADER)] for row in values[1:]]
    original_count = len(existing)
    index = EventIndex(existing)
    touched, counts = set(), {"new": 0, "updated": 0, "same": 0}
    for event in events:
        status, i = index.merge(event, now)
        counts[status] += 1
        if i < original_count:
            touched.add(i)  # Last seen changes even when nothing else does
    new_rows = index.rows[original_count:]
    if not dry_run:
        updates = [{"range": f"A{i + 2}:J{i + 2}", "values": [index.rows[i]]} for i in sorted(touched)]
        if updates:
            tab.batch_update(updates)
        if new_rows:
            tab.append_rows(new_rows, value_input_option="RAW")
    return counts, new_rows
