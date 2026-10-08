import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db import get_db
from app.seed import SEED_PATH, reset_database


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch("app.db.DB_PATH", Path(self.temp.name) / "test.sqlite3")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_reset_restores_data_and_next_id(self):
        reset_database()
        with get_db() as db:
            db.execute("UPDATE customers SET phone = '0987654321' WHERE id = 2")
            db.execute(
                "INSERT INTO customers (name, email, phone) VALUES (?, ?, ?)",
                ("Lê Minh Anh", "minhanh@example.com", "0901234567"),
            )
        for _ in range(2):
            self.assertEqual(reset_database(), 4)
            with get_db() as db:
                actual = [dict(row) for row in db.execute("SELECT * FROM customers ORDER BY id")]
            expected = json.loads(SEED_PATH.read_text(encoding="utf-8"))["customers"]
            self.assertEqual(actual, expected)
        with get_db() as db:
            cursor = db.execute(
                "INSERT INTO customers (name, email, phone) VALUES (?, ?, ?)",
                ("Lê Minh Anh", "minhanh@example.com", "0901234567"),
            )
            self.assertEqual(cursor.lastrowid, 5)

    def test_invalid_seed_preserves_existing_data(self):
        reset_database()
        payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        payload["customers"][1]["email"] = payload["customers"][0]["email"]
        invalid = Path(self.temp.name) / "invalid.json"
        invalid.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaises(ValueError):
            reset_database(invalid)
        with get_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM customers").fetchone()[0], 4)


if __name__ == "__main__":
    unittest.main()
