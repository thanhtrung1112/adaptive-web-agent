import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.seed import reset_database


class CustomerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        patcher = patch("app.db.DB_PATH", Path(temp.name) / "test.sqlite3")
        patcher.start()
        self.addCleanup(patcher.stop)
        reset_database()
        self.client = self.enterContext(TestClient(app))

    def test_search_then_detail_records_view_only_after_opening(self):
        endpoint = "/api/session/last_viewed_customer"
        self.assertFalse(self.client.get(endpoint).json()["viewed"])
        response = self.client.get("/customers", params={"email": " TRAN.HOA@example.com "})
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/customers/1"', response.text)
        self.assertNotIn("nguyen.dung@example.com", response.text)
        self.client.get("/api/customers", params={"email": "tran.hoa@example.com"})
        self.assertFalse(self.client.get(endpoint).json()["viewed"])
        self.assertEqual(self.client.get("/customers/1").status_code, 200)
        self.assertEqual(self.client.get(endpoint).json()["email"], "tran.hoa@example.com")
        with TestClient(app) as other:
            self.assertFalse(other.get(endpoint).json()["viewed"])
            other.get("/customers/2")
            self.assertEqual(other.get(endpoint).json()["email"], "nguyen.dung@example.com")
        self.assertEqual(self.client.get(endpoint).json()["email"], "tran.hoa@example.com")

    def test_missing_customer_does_not_record_view(self):
        response = self.client.get("/customers", params={"email": "missing@example.com"})
        self.assertIn("Không tìm thấy khách hàng phù hợp.", response.text)
        self.assertEqual(self.client.get("/customers/9999").status_code, 404)
        self.assertFalse(self.client.get("/api/session/last_viewed_customer").json()["viewed"])

    def test_t003_updates_only_target_phone(self):
        before = self.client.get("/api/customers").json()["customers"]
        result = self.client.get("/customers", params={"email": "nguyen.dung@example.com"})
        self.assertIn('href="/customers/2"', result.text)
        self.assertIn('href="/customers/2/edit"', self.client.get("/customers/2").text)
        form = self.client.get("/customers/2/edit")
        self.assertEqual(form.status_code, 200)
        self.assertIn('value="0900000002"', form.text)
        response = self.client.post(
            "/customers/2/edit", data={"phone": "0987654321"}, follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/customers/2")
        expected = [dict(customer) for customer in before]
        expected[1]["phone"] = "0987654321"
        self.assertEqual(self.client.get("/api/customers").json()["customers"], expected)
        result = self.client.get("/api/customers", params={"email": "nguyen.dung@example.com"}).json()
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["customers"][0]["phone"], "0987654321")

    def test_invalid_edit_preserves_data(self):
        before = self.client.get("/api/customers").json()
        for values in ({}, {"phone": "   "}):
            response = self.client.post("/customers/2/edit", data=values)
            self.assertEqual(response.status_code, 400)
            self.assertIn("Vui lòng nhập số điện thoại.", response.text)
        self.assertEqual(self.client.get("/customers/9999/edit").status_code, 404)
        self.assertEqual(self.client.post("/customers/9999/edit", data={"phone": "123"}).status_code, 404)
        self.assertEqual(self.client.get("/api/customers").json(), before)

    def test_t001_create_still_works(self):
        self.assertEqual(self.client.get("/customers/new").status_code, 200)
        values = {"name": "Lê Minh Anh", "email": "minhanh@example.com", "phone": "0901234567"}
        response = self.client.post("/customers/new", data=values, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.client.post("/customers/new", data=values).status_code, 400)
        result = self.client.get("/api/customers", params={"email": values["email"]}).json()
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["customers"][0]["phone"], values["phone"])


if __name__ == "__main__":
    unittest.main()
