from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import database.db as db


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "test.db"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.old_path
        self.tmpdir.cleanup()

    def test_user_address_roundtrip(self) -> None:
        db.upsert_user(1, "tester", "Test")
        db.set_user_address(1, "Рівне", "Київська", "12", "2", "1")
        row = db.get_user(1)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["city"], "Рівне")
        self.assertEqual(row["street"], "Київська")
        self.assertEqual(row["house"], "12")
        self.assertEqual(row["queue"], "2")
        self.assertEqual(row["subqueue"], "1")

    def test_schedule_queries(self) -> None:
        db.save_schedule("2026-04-01", "2.1", "08:00", "10:00")
        db.save_schedule("2026-04-01", "2.1", "14:00", "16:00")
        db.save_schedule("2026-04-01", "3.1", "09:00", "11:00")

        queue_rows = db.get_schedule_for("2026-04-01", "2.1")
        self.assertEqual(len(queue_rows), 2)

        grouped = db.get_schedule_for_date("2026-04-01")
        self.assertIn("2.1", grouped)
        self.assertIn("3.1", grouped)
        self.assertEqual(grouped["2.1"], ["08:00-10:00", "14:00-16:00"])


if __name__ == "__main__":
    unittest.main()
