import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.seed import reset_database
from app.db import get_db


# Mỗi kiểm thử dùng database riêng, không thay đổi dữ liệu người dùng.
class OrderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        patcher = patch("app.db.DB_PATH", Path(temp.name) / "test.sqlite3")
        patcher.start()
        self.addCleanup(patcher.stop)
        reset_database()
        self.client = self.enterContext(TestClient(app))

    # T004 phải có đúng một đơn pending và hai dòng SKU đúng số lượng.
    def test_t004_and_reset(self):
        self.assertEqual(self.client.get("/orders").status_code, 200)
        form = self.client.get("/orders/new")
        self.assertEqual(form.status_code, 200)
        self.assertIn("SKU-205", form.text)
        payload = {"customer_id": "3", "sku": ["SKU-100", "SKU-205"], "qty": ["1", "3"]}
        result = self.client.post("/orders/new", data=payload, follow_redirects=False)
        self.assertEqual(result.status_code, 303)
        self.assertEqual(self.client.get(result.headers["location"]).status_code, 200)
        data = self.client.get("/api/orders", params={"customer_email": "pham.ha@example.com"}).json()
        self.assertEqual(data["count"], 1)
        order = data["orders"][0]
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["items"], [{"sku": "SKU-100", "qty": 1}, {"sku": "SKU-205", "qty": 3}])
        self.assertEqual(self.client.get("/api/orders/" + order["id"]).json(), order)
        for _ in range(2):
            reset_database()
            self.assertEqual(self.client.get("/api/orders").json()["count"], 1)
            self.assertEqual(self.client.get("/api/orders/ORD-1003").json()["status"], "shipped")
            self.assertEqual(self.client.get("/api/orders?customer_email=pham.ha@example.com").json()["count"], 0)
            with get_db() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM products").fetchone()[0], 2)

    # Dữ liệu không hợp lệ không được tạo đơn rỗng hay lưu một phần.
    def test_invalid_forms_do_not_write(self):
        cases = [
            {"customer_id": "999", "sku": "SKU-100", "qty": "1"},
            {"customer_id": "3", "sku": "UNKNOWN", "qty": "1"},
            {"customer_id": "3", "sku": ["SKU-100", "SKU-100"], "qty": ["1", "2"]},
            {"customer_id": "3", "sku": ["SKU-100", "SKU-205"], "qty": "1"},
            {"customer_id": "3"},
        ]
        for qty in ["0", "-1", "1.5", "abc", "", "1000001"]:
            cases.append({"customer_id": "3", "sku": "SKU-100", "qty": qty})
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/orders/new", data=payload).status_code, 400)
        self.assertEqual(self.client.get("/api/orders").json()["count"], 1)
        with get_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0], 1)
        self.assertEqual(self.client.get("/orders/ORD-9999").status_code, 404)


    # T005 thay đúng trạng thái; reset khôi phục trạng thái trước khi thao tác.
    def test_t005_status_update_and_reset(self):
        before = self.client.get("/api/orders/ORD-1003").json()
        self.assertEqual(before["status"], "shipped")
        page = self.client.get("/orders/ORD-1003")
        self.assertIn('value="delivered"', page.text)
        result = self.client.post("/orders/ORD-1003/status", data={"status": "delivered"}, follow_redirects=False)
        self.assertEqual(result.status_code, 303)
        expected = {**before, "status": "delivered"}
        self.assertEqual(self.client.get("/api/orders/ORD-1003").json(), expected)
        self.assertIn("Đã giao", self.client.get(result.headers["location"]).text)
        reset_database()
        self.assertEqual(self.client.get("/api/orders/ORD-1003").json(), before)

    # Trạng thái lạ hoặc mã đơn không tồn tại phải bị từ chối, không ghi dữ liệu.
    def test_invalid_status_leaves_order_unchanged(self):
        before = self.client.get("/api/orders").json()
        for status in ["unknown", "", "DELIVERED"]:
            self.assertEqual(self.client.post("/orders/ORD-1003/status", data={"status": status}).status_code, 400)
        self.assertEqual(self.client.post("/orders/ORD-9999/status", data={"status": "delivered"}).status_code, 404)
        self.assertEqual(self.client.get("/api/orders").json(), before)


if __name__ == "__main__":
    unittest.main()
