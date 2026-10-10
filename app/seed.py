"""Reset CRM và Order về seed cố định. Không gọi khi server khởi động."""

import json
from pathlib import Path

from app.db import get_db, init_db


SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_v1.json"


# Kiểm tra seed trước khi xóa; toàn bộ thay đổi dữ liệu nằm trong một transaction.
def reset_database(seed_path: Path = SEED_PATH) -> int:
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    if payload.get("seed") != "seed_v1" or payload.get("scope") != "crm_order_support":
        raise ValueError("Cần seed_v1 đầy đủ CRM, Order và Support.")

    customers = payload["customers"]
    if not isinstance(customers, list) or not customers:
        raise ValueError("Seed phải chứa danh sách khách hàng không rỗng.")

    rows = []
    for customer in customers:
        if type(customer.get("id")) is not int or customer["id"] < 1:
            raise ValueError("ID khách hàng phải là số nguyên dương.")
        for field in ("name", "email", "phone"):
            if not isinstance(customer.get(field), str) or not customer[field].strip():
                raise ValueError(f"Trường {field} phải là chuỗi không rỗng.")
        rows.append((customer["id"], customer["name"], customer["email"], customer["phone"]))

    if len({row[0] for row in rows}) != len(rows):
        raise ValueError("Seed bị trùng ID.")
    if len({row[2].strip().lower() for row in rows}) != len(rows):
        raise ValueError("Seed bị trùng email.")

    # Sản phẩm phải hợp lệ và không trùng SKU trước khi đụng vào database.
    products = payload["products"]
    if not isinstance(products, list) or not products:
        raise ValueError("Seed phải có sản phẩm.")
    product_rows = []
    for product in products:
        if any(not isinstance(product.get(key), str) or not product[key].strip()
               for key in ("sku", "name")):
            raise ValueError("SKU và tên sản phẩm không được rỗng.")
        if type(product.get("price")) is not int or product["price"] < 0:
            raise ValueError("Giá phải là số nguyên không âm.")
        product_rows.append((product["sku"], product["name"], product["price"]))
    if len({row[0] for row in product_rows}) != len(product_rows):
        raise ValueError("Seed bị trùng SKU.")

    # Đơn mẫu dùng ID cố định: ID 3 được hiển thị là ORD-1003.
    orders = payload.get("orders", [])
    customer_ids = {row[0] for row in rows}
    skus = {row[0] for row in product_rows}
    seen_ids = set()
    for order in orders:
        if type(order.get("id")) is not int or order["id"] <= 0 or order["id"] in seen_ids:
            raise ValueError("ID đơn mẫu không hợp lệ hoặc bị trùng.")
        seen_ids.add(order["id"])
        if order["customer_id"] not in customer_ids or order["status"] not in {
            "pending", "confirmed", "shipped", "delivered", "cancelled"
        }:
            raise ValueError("Khách hàng hoặc trạng thái đơn mẫu không hợp lệ.")
        if not order.get("items"):
            raise ValueError("Đơn mẫu phải có sản phẩm.")
        seen_skus = set()
        for item in order["items"]:
            if item["sku"] not in skus or item["sku"] in seen_skus:
                raise ValueError("SKU đơn mẫu không hợp lệ hoặc bị trùng.")
            seen_skus.add(item["sku"])
            if type(item["qty"]) is not int or item["qty"] <= 0:
                raise ValueError("Số lượng đơn mẫu phải là số nguyên dương.")

    # Kiểm tra quan hệ Support trước khi xóa dữ liệu hiện tại.
    staff = payload["staff"]
    tickets = payload["tickets"]
    staff_ids = {member["id"] for member in staff}
    if len(staff_ids) != len(staff) or any(type(m["id"]) is not int or m["id"] <= 0 or not m["name"].strip() for m in staff):
        raise ValueError("Nhân viên mẫu không hợp lệ.")
    ticket_ids = set()
    for ticket in tickets:
        if type(ticket["id"]) is not int or ticket["id"] <= 0 or ticket["id"] in ticket_ids:
            raise ValueError("ID ticket không hợp lệ hoặc trùng.")
        ticket_ids.add(ticket["id"])
        if ticket["order_id"] not in seen_ids or ticket["status"] not in {"open", "in_progress", "closed"}:
            raise ValueError("Đơn hoặc trạng thái ticket không hợp lệ.")
        if ticket["assignee_id"] is not None and ticket["assignee_id"] not in staff_ids:
            raise ValueError("Người xử lý ticket không tồn tại.")
        if not ticket["subject"].strip() or not isinstance(ticket["note"], str):
            raise ValueError("Nội dung ticket không hợp lệ.")

    init_db()
    with get_db() as db:
        # Khi thêm Order/Support, cần mở rộng reset theo quan hệ dữ liệu.
        tables = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if tables - {"customers", "products", "orders", "order_items", "staff", "tickets", "sqlite_sequence"}:
            raise ValueError("Database có bảng mới. Hãy mở rộng reset trước khi chạy.")

        # Xóa bảng con trước bảng cha để bảo toàn ràng buộc khóa ngoại.
        db.execute("DELETE FROM tickets")
        db.execute("DELETE FROM staff")
        db.execute("DELETE FROM order_items")
        db.execute("DELETE FROM orders")
        db.execute("DELETE FROM products")
        db.execute("DELETE FROM customers")
        db.execute("DELETE FROM sqlite_sequence WHERE name IN ('customers', 'orders', 'tickets')")
        db.executemany(
            "INSERT INTO customers (id, name, email, phone) VALUES (?, ?, ?, ?)",
            rows,
        )
        db.executemany("INSERT INTO products (sku, name, price) VALUES (?, ?, ?)", product_rows)
        # Nạp đơn sau khách hàng/sản phẩm, rồi mới nạp các dòng chi tiết.
        for order in orders:
            db.execute(
                "INSERT INTO orders (id, customer_id, status, created_at) VALUES (?, ?, ?, ?)",
                (order["id"], order["customer_id"], order["status"], order["created_at"]),
            )
            db.executemany(
                "INSERT INTO order_items (order_id, sku, qty) VALUES (?, ?, ?)",
                [(order["id"], item["sku"], item["qty"]) for item in order["items"]],
            )
        # Nạp ticket sau đơn và nhân viên để khóa ngoại luôn hợp lệ.
        db.executemany("INSERT INTO staff(id,name) VALUES (?,?)", [(m["id"], m["name"]) for m in staff])
        db.executemany("INSERT INTO tickets(id,order_id,subject,status,assignee_id,note) VALUES (?,?,?,?,?,?)",
                       [(t["id"],t["order_id"],t["subject"],t["status"],t["assignee_id"],t["note"]) for t in tickets])
    return len(rows)
