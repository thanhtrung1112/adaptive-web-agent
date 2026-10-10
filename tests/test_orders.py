import csv
import io
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
            self.assertEqual(self.client.get("/api/orders").json()["count"], 5)
            self.assertEqual(self.client.get("/api/orders/ORD-1003").json()["status"], "shipped")
            self.assertEqual(self.client.get("/api/orders?customer_email=pham.ha@example.com").json()["count"], 0)
            with get_db() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0], 5)
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
        self.assertEqual(self.client.get("/api/orders").json()["count"], 5)
        with get_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0], 5)
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


    # So sánh tập ID CSV với API và tập mong đợi độc lập, gồm cả hai biên ngày.
    def test_t006_filter_and_csv(self):
        params = {"from": "2026-09-01", "to": "2026-09-15"}
        result = self.client.get("/api/orders", params=params).json()
        expected = ["ORD-1002", "ORD-1003", "ORD-1004"]
        self.assertEqual([order["id"] for order in result["orders"]], expected)
        self.assertEqual(result["count"], 3)
        page = self.client.get("/orders", params=params)
        self.assertEqual(page.status_code, 200)
        self.assertIn("from=2026-09-01&amp;to=2026-09-15", page.text)
        self.assertNotIn("ORD-1001", page.text)
        download = self.client.get("/orders/export.csv", params=params)
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download.headers["content-disposition"])
        rows = list(csv.DictReader(io.StringIO(download.content.decode("utf-8-sig"))))
        self.assertEqual([row["id"] for row in rows], expected)
        combined = self.client.get("/api/orders", params={**params, "customer_email": "tran.hoa@example.com"}).json()
        self.assertEqual([order["id"] for order in combined["orders"]], ["ORD-1003"])

    # Khoảng rỗng xuất CSV chỉ có tiêu đề; ngày sai bị từ chối ở cả ba đầu vào.
    def test_date_errors_and_empty_csv(self):
        for params in [{"from": "2026-09-16", "to": "2026-09-01"},
                       {"from": "2026-02-30"}, {"to": "bad-date"}]:
            for path in ["/orders", "/api/orders", "/orders/export.csv"]:
                self.assertEqual(self.client.get(path, params=params).status_code, 400)
        params = {"from": "2025-01-01", "to": "2025-01-01"}
        self.assertEqual(self.client.get("/api/orders", params=params).json()["count"], 0)
        result = self.client.get("/orders/export.csv", params=params)
        self.assertEqual(list(csv.DictReader(io.StringIO(result.content.decode("utf-8-sig")))), [])
        for params, count in [({"from": "2026-09-15"}, 2), ({"to": "2026-09-01"}, 2), ({}, 5)]:
            self.assertEqual(self.client.get("/api/orders", params=params).json()["count"], count)


if __name__ == "__main__":
    unittest.main()
