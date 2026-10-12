import unittest
from datetime import date, datetime, timedelta

from event_rules import find_city, find_event_date, india_signal, is_event_topic
from events_sheet import EVENTS_HEADER, EventIndex, LINKS, SOURCES, LAST_SEEN
from fetch_events import IST, MAX_GAP, MIN_GAP, WINDOW_END, WINDOW_START, daily_plan, due_slot


class TopicTests(unittest.TestCase):
    def test_investor_events(self):
        for text in [
            "Founders & Investors Xplore by CEDAT",
            "The Founders X Investors Pitch | 25th October | Mumbai",
            "eChai Startup Demo Day in Bengaluru",
            "Angel investors meet for early-stage startups, Pune",
            "Pune Founders Conclave | The Pitch Room",
            "Startup India roadshow in Guwahati",
        ]:
            self.assertTrue(is_event_topic(text), text)

    def test_noise(self):
        for text in [
            "Swan Defence sets investor meet dates for Oct 13-24 on NSE",
            "India Retail investors Expo & Conference",
            "Startup raises $5 Mn led by Accel",
            "Mega job fair for freshers in Noida",
        ]:
            self.assertFalse(is_event_topic(text), text)

    def test_city_and_india(self):
        self.assertEqual(find_city("Meetup at HSR Layout, Bangalore"), "Bengaluru")
        self.assertEqual(find_city("Join us in Gurgaon"), "Delhi NCR")
        self.assertEqual(find_city("Live on Zoom"), "Online")
        self.assertTrue(india_signal("Prize pool of ₹10 lakh"))
        self.assertFalse(india_signal("Demo day in San Francisco"))


class DateTests(unittest.TestCase):
    ref = date(2026, 10, 12)

    def test_formats(self):
        cases = {
            "Join us on 25th October": date(2026, 10, 25),
            "Event on Nov 5, 2026 in Pune": date(2026, 11, 5),
            "5-6 December, Bengaluru": date(2026, 12, 5),
            "Date: 14/11/2026": date(2026, 11, 14),
            "Starts 2026-10-30": date(2026, 10, 30),
            "Demo day on 10 Jan": date(2027, 1, 10),
        }
        for text, expected in cases.items():
            self.assertEqual(find_event_date(text, self.ref), expected, text)

    def test_past_and_deadline(self):
        self.assertIsNone(find_event_date("Held on 2 October 2026", self.ref))
        # The deadline is skipped; the event date is used
        self.assertEqual(find_event_date("Apply by 20 Oct. Demo day on 30 Oct", self.ref), date(2026, 10, 30))


class ScheduleTests(unittest.TestCase):
    def test_plan_bounds(self):
        day = date(2026, 1, 1)
        for i in range(400):
            plan = daily_plan(day + timedelta(days=i))
            self.assertEqual(len(plan), 3)
            self.assertGreaterEqual(plan[0], WINDOW_START)
            self.assertLessEqual(plan[2], WINDOW_END)
            for a, b in zip(plan, plan[1:]):
                self.assertTrue(MIN_GAP <= b - a <= MAX_GAP)

    def test_due_slot(self):
        day = date(2026, 10, 12)
        plan = daily_plan(day)
        at = lambda minutes: datetime(2026, 10, 12, minutes // 60, minutes % 60, tzinfo=IST)
        self.assertIsNone(due_slot(at(plan[0] - 1), []))
        self.assertEqual(due_slot(at(plan[0] + 5), []), plan[0])
        self.assertIsNone(due_slot(at(plan[0] + 20), [at(plan[0] + 5)]))
        self.assertEqual(due_slot(at(plan[1] + 3), [at(plan[0] + 5)]), plan[1])
        # Missed the first slot entirely: catch up once, then wait 2 hours before the next
        late = at(plan[1] + 1)
        self.assertEqual(due_slot(late, []), plan[0])
        self.assertIsNone(due_slot(late + timedelta(minutes=15), [late]))


class MergeTests(unittest.TestCase):
    def event(self, **kw):
        base = {"name": "Founders Meet", "date": "2026-10-25", "city": "Pune", "organizer": "",
                "reg_link": "https://lu.ma/abc", "source": "Luma", "link": "https://lu.ma/abc", "author": ""}
        base.update(kw)
        return base

    def test_merge_by_link_and_name(self):
        index = EventIndex([])
        self.assertEqual(index.merge(self.event(), "t1")[0], "new")
        # Same registration link from LinkedIn -> merged into the same row
        status, i = index.merge(self.event(name="Founders Meet Pune!", source="LinkedIn",
                                           link="https://www.linkedin.com/feed/update/urn:li:activity:1/",
                                           author="https://www.linkedin.com/in/x"), "t2")
        self.assertEqual((status, i), ("updated", 0))
        # Same name + date, different link -> merged too
        status, _ = index.merge(self.event(name="founders  meet", reg_link="", link="https://news.example/a",
                                           source="News - Inc42"), "t3")
        self.assertEqual(status, "updated")
        row = index.rows[0]
        self.assertEqual(row[SOURCES].split("\n"), ["Luma", "LinkedIn", "News - Inc42"])
        self.assertEqual(len(row[LINKS].split("\n")), 3)
        self.assertEqual(row[LAST_SEEN], "t3")
        self.assertEqual(len(index.rows), 1)
        self.assertEqual(len(row), len(EVENTS_HEADER))
        # Different date -> a new event
        self.assertEqual(index.merge(self.event(date="2026-11-25", reg_link="", link="https://x.y/z"), "t4")[0], "new")


if __name__ == "__main__":
    unittest.main()
