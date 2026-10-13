import unittest
from datetime import date, datetime, timedelta

from event_rules import (event_index, find_city, find_city_near, find_event_date, india_signal, is_event_specific_link,
                         is_event_topic, is_india_event, link_key, pick_registration_link)
from event_sources import _article_body
from events_sheet import EVENTS_HEADER, EventIndex, LINKS, SOURCES, LAST_SEEN
from fetch_events import IST, runs_logged_today


class TopicTests(unittest.TestCase):
    def test_investor_events(self):
        for text in [
            "Founders & Investors Xplore by CEDAT",
            "The Founders X Investors Pitch | 25th October | Mumbai",
            "eChai Startup Demo Day in Bengaluru",
            "Angel investors meet for early-stage startups, Pune",
            "Pune Founders Conclave | The Pitch Room",
            "Pitch to 30+ investors at our Demo Day",
            "Meet angel investors in Delhi | In person",
            "VC office hours for pre-seed founders, Bengaluru",
        ]:
            self.assertTrue(is_event_topic(text), text)

    def test_general_startup_events(self):
        # Only events whose main purpose is founders meeting / pitching to investors count
        for text in [
            "Startup India roadshow in Guwahati",
            "Startup Summit 2026, Bengaluru: 5000 founders, 100 speakers",
            "E-Summit 2026 at IIT Bombay",
            "Founders networking mixer in Gurugram this Friday",
            "Fundraising workshop for first-time founders",
        ]:
            self.assertFalse(is_event_topic(text), text)

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


class RunLogTests(unittest.TestCase):
    def test_runs_logged_today(self):
        values = [["Run time (IST)"], ["2026-10-11 18:00", "x"], ["2026-10-12 09:40", "x"], ["bad"]]
        self.assertEqual(len(runs_logged_today(values, date(2026, 10, 12))), 1)
        self.assertEqual(runs_logged_today(values, date(2026, 10, 13)), [])


class ReviewFixTests(unittest.TestCase):
    def test_single_words_dont_exclude(self):
        self.assertTrue(is_event_topic("Excited to share: Founders & Investors Mixer in Bengaluru on 25 Oct"))
        self.assertTrue(is_event_topic("Demo day: options for founders to meet 20 investors"))
        self.assertFalse(is_event_topic("Investor meet: Swan Defence shares to watch on NSE"))
        self.assertFalse(is_event_topic("Let's connect! We're investing in fintech founders"))

    def test_dates(self):
        self.assertIsNone(find_event_date("Our demo day held on 5 September saw 20 startups", date(2026, 10, 10)))
        self.assertEqual(find_event_date("Investor meet on 10 Jan in Pune", date(2026, 12, 20)), date(2027, 1, 10))
        self.assertIsNone(find_event_date("Indian founders, pitch to us by 30 October", date(2026, 10, 12)))
        self.assertEqual(find_event_date("Hosted by Accel on 5 Nov in Bengaluru", date(2026, 10, 12)), date(2026, 11, 5))

    def test_india_and_city(self):
        self.assertFalse(is_india_event("Indian founders in the Bay Area: mixer in San Francisco on Nov 5"))
        self.assertTrue(is_india_event("Investor meet in Pune with investors from Dubai"))
        self.assertFalse(india_signal("We tie up with founders in Singapore"))
        text = "We invest at pre-seed. Founders in Bengaluru, DM us. Investor meet in Mumbai on 20 Nov."
        self.assertEqual(find_city_near(text, event_index(text)), "Mumbai")

    def test_links(self):
        self.assertEqual(link_key("https://www.luma.com/abc/?utm_source=x"), link_key("lu.ma/abc"))
        self.assertEqual(link_key("https://www.eventbrite.co.in/e/x-123"), "eventbrite.com/e/x-123")
        self.assertNotEqual(link_key("https://forms.office.com/Pages/ResponsePage.aspx?id=AAA", True),
                            link_key("https://forms.office.com/Pages/ResponsePage.aspx?id=BBB", True))
        self.assertFalse(is_event_specific_link("https://linktr.ee/org"))
        self.assertFalse(is_event_specific_link("https://bit.ly/4aa6nJp"))
        self.assertFalse(is_event_specific_link("https://www.meetup.com/group-x/"))
        self.assertTrue(is_event_specific_link("https://www.meetup.com/group-x/events/123/"))
        self.assertEqual(pick_registration_link(["https://bit.ly/abc", "https://linktr.ee/x", "https://lu.ma/evt"]),
                         "https://lu.ma/evt")

    def test_second_review_fixes(self):
        d = date(2026, 10, 12)
        self.assertEqual(find_event_date("Investor meetup from 10 AM till 1 PM on 25 October, Bengaluru", d), date(2026, 10, 25))
        self.assertEqual(find_event_date("Register by 25 Oct; summit 2 Nov", d), date(2026, 11, 2))
        self.assertEqual(find_event_date("Deadline: 30 Oct | Event: 5 Nov, Bengaluru investor meet", d), date(2026, 11, 5))
        self.assertEqual(find_event_date("Investor meet on 25 Oct 1500 founders", d), date(2026, 10, 25))
        self.assertFalse(is_india_event("Calling Mumbai startups: pitch to investors at the Founders Summit in Dubai on 5 Nov"))
        self.assertTrue(is_event_topic("Meet 50+ angel and institutional investors at our Demo Day in Bengaluru on 5 Nov"))
        self.assertFalse(is_event_specific_link("https://10times.com/india/startup"))
        self.assertFalse(is_event_specific_link("https://lu.ma/"))

    def test_government_filter(self):
        from fetch_vc_news import is_relevant
        self.assertFalse(is_relevant("Govt raises windfall tax on crude oil"))
        self.assertTrue(is_relevant("Government launches Rs 10,000 crore fund of funds for startups"))
        self.assertTrue(is_relevant("Data centre startup Nxtra raises $50 Mn led by Blume Ventures"))
        self.assertTrue(is_relevant("Zepto raises $200 Mn as government eases norms"))

    def test_article_body_skips_site_links(self):
        page = ('<html><header><a href="https://bit.ly/follow">Follow us</a></header><nav><a href="/x">x</a></nav>'
                '<article><p>' + "Investor meet in Pune on 5 Nov. " * 10 + '<a href="https://lu.ma/evt">Register</a></p></article>'
                '<footer><a href="https://linktr.ee/site">links</a></footer></html>')
        body = _article_body(page)
        self.assertIn("lu.ma/evt", body)
        self.assertNotIn("bit.ly/follow", body)
        self.assertNotIn("linktr.ee/site", body)


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

    def test_organiser_pages_and_dates(self):
        index = EventIndex([])
        index.merge(self.event(reg_link="https://linktr.ee/org", link="https://li/1"), "t1")
        # Same linktr.ee, different event -> its own row
        self.assertEqual(index.merge(self.event(name="Pitch Night", date="2026-11-02", reg_link="https://linktr.ee/org",
                                                link="https://x/9"), "t2")[0], "new")
        # Same Luma event under luma.com, same date -> merged; same link with another date -> new row
        index.merge(self.event(name="Demo Day", date="2026-12-01", reg_link="https://lu.ma/demo", link="https://lu.ma/demo"), "t3")
        self.assertEqual(index.merge(self.event(name="zzz", date="2026-12-01", reg_link="https://luma.com/demo/",
                                                link="https://x/10"), "t4")[0], "updated")
        self.assertEqual(index.merge(self.event(name="Demo Day 2", date="2027-03-01", reg_link="https://lu.ma/demo",
                                                link="https://x/11"), "t5")[0], "new")

    def test_extra_links_kept(self):
        index = EventIndex([])
        index.merge(self.event(link="https://inc42.com/a", extra_links=["https://news.google.com/rss/articles/X"]), "t1")
        self.assertIn("https://news.google.com/rss/articles/X", index.rows[0][LINKS].split("\n"))


if __name__ == "__main__":
    unittest.main()
