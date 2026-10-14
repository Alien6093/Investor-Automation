import unittest
from datetime import datetime

from fetch_vc_news import is_relevant
from investor_screen import add_screen_columns, amount_usd, is_seed_stage, label, lead_keys, screen, to_qualify_table
from sectors import tag_sectors


class RelevanceTests(unittest.TestCase):
    def test_deals_with_everyday_words_are_kept(self):
        # Words dropped from the merged branch's exclusion list: they appear in real deals
        for title in [
            "Gold-loan startup Rupeek raises $10 Mn led by Accel",
            "Order-management startup bags Rs 20 Cr in Series A",
            "Tax-filing platform secures seed funding from Blume Ventures",
            "Award-winning creator platform raises $3M seed round",
            "Contract manufacturing startup nets $5 Mn",
        ]:
            self.assertTrue(is_relevant(title), title)

    def test_stock_market_noise_is_dropped(self):
        for title in [
            "Brokerage raises target price on Infosys shares",
            "Sovereign gold bond: should you invest?",
            "Sensex ends higher as investors cheer Q2 results",
        ]:
            self.assertFalse(is_relevant(title), title)

    def test_investment_wording(self):
        self.assertTrue(is_relevant("Blume Ventures invests in creator-tech platform Trell"))
        self.assertTrue(is_relevant("Why we invested in Acme"))


class SectorTests(unittest.TestCase):
    def test_tags(self):
        self.assertIn("Influencer Marketing", tag_sectors("Influencer marketing platform Plixxo raises $2M"))
        self.assertIn("Marketing / AdTech", tag_sectors("Adtech startup raises seed round"))


class ScreenTests(unittest.TestCase):
    def test_amounts_and_stage(self):
        self.assertAlmostEqual(amount_usd("$5 Mn"), 5e6)
        self.assertAlmostEqual(amount_usd("₹40 Cr"), 40e7 / 88)
        self.assertIsNone(amount_usd("Series A"))
        self.assertTrue(is_seed_stage("Seed", ""))
        self.assertTrue(is_seed_stage("", "$2 Mn"))
        self.assertFalse(is_seed_stage("Series B", "$2 Mn"))
        self.assertFalse(is_seed_stage("", "$20 Mn"))

    def test_leads(self):
        self.assertEqual(lead_keys("Acme raises $3M led by Blume Ventures and Accel"), {"blume", "accel"})
        self.assertEqual(lead_keys("Fireside Ventures leads $5 Mn round in Chosen"), {"fireside"})

    def test_screen_and_to_qualify(self):
        rows = [
            ["2026-09-10 10:00", "Inc42", "Creator platform Acme raises $2 Mn seed round led by Blume Ventures", "Startup Funding",
             "https://x/1", "Acme", "$2 Mn", "Seed", "Blume Ventures; Angel X", "Creator Economy"],
            ["2024-01-10 10:00", "TechCrunch", "Beta raises $50M Series C led by Old Capital", "Startup Funding",
             "https://x/2", "Beta", "$50M", "Series C", "Old Capital", "Fintech"],
        ]
        stats = screen(rows, today=datetime(2026, 10, 14))
        self.assertEqual(stats["blume"]["seed"], 1)
        self.assertEqual(stats["blume"]["led"], 1)
        self.assertEqual(stats["blume"]["india"], 1)
        self.assertEqual(stats["blume"]["adjacent"], 1)
        self.assertFalse(stats["old"]["active"])
        table = add_screen_columns([["Blume Ventures", "VC / PE Fund"], ["Old Capital", "VC / PE Fund"],
                                    ["Angel X", "Angel / Network"]], stats)
        self.assertEqual([r[-1] for r in table], ["Strong candidate", "No deal in 12 months (inactive?)",
                                                  "Skip by default (angel / family office)"])
        self.assertEqual([r[0] for r in to_qualify_table(table, stats, [])], ["Blume Ventures"])
        # Already in the Qualifier tab: not listed again
        self.assertEqual(to_qualify_table(table, stats, ["Blume Ventures"]), [])
        self.assertEqual(label("VC / PE Fund", None), "No deals seen")


if __name__ == "__main__":
    unittest.main()
