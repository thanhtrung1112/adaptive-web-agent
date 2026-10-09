import csv
import io
from datetime import date, datetime, timezone
from urllib.parse import urlencode
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.db import get_db


router = APIRouter()
# Nhãn tiếng Việt trên giao diện tương ứng giá trị chuẩn dùng trong API/database.
ORDER_STATUSES = {
    "pending": "Chờ xác nhận", "confirmed": "Đã xác nhận",
    "shipped": "Đang giao", "delivered": "Đã giao", "cancelled": "Đã hủy",
}
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


# Đọc đơn cùng khách hàng và từng sản phẩm để giao diện/API dùng chung dữ liệu.
def read_orders(customer_email: str | None = None, date_from: str = "", date_to: str = ""):
    sql = """SELECT o.*, c.name AS customer_name, c.email AS customer_email
             FROM orders o JOIN customers c ON c.id = o.customer_id"""
    params = []
    conditions = []
    if customer_email is not None:
        conditions.append("c.email = ?")
        params.append(customer_email.strip().lower())
    # Ngày UTC, lấy cả hai đầu mút; dùng chung cho HTML, API và CSV.
    validate_dates(date_from, date_to)
    if date_from:
        conditions.append("date(o.created_at) >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date(o.created_at) <= ?")
        params.append(date_to)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    with get_db() as db:
        orders = [dict(row) for row in db.execute(sql + " ORDER BY o.id", params)]
        for order in orders:
            order["id"] = f"ORD-{order['id'] + 1000}"
            internal_id = int(order["id"][4:]) - 1000
            order["items"] = [dict(row) for row in db.execute(
                "SELECT sku, qty FROM order_items WHERE order_id = ? ORDER BY sku", (internal_id,)
            )]
    return orders


# Chặn ngày sai định dạng và khoảng ngày đảo ngược trước khi truy vấn.
def validate_dates(date_from, date_to):
    for value in (date_from, date_to):
        if value:
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() != value:
                    raise ValueError()
            except ValueError:
                raise HTTPException(400, "Ngày phải có định dạng YYYY-MM-DD và tồn tại.")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "Từ ngày không được lớn hơn Đến ngày.")


# Hiển thị danh sách và giữ điều kiện lọc trên liên kết tải CSV.
@router.get("/orders", response_class=HTMLResponse)
def list_orders(request: Request, date_from: str = Query("", alias="from"), date_to: str = Query("", alias="to")):
    error = None
    try:
        orders = read_orders(date_from=date_from, date_to=date_to)
    except HTTPException as exc:
        error = exc.detail
        orders = []
    return templates.TemplateResponse(
        request=request, name="orders/list.html",
        status_code=400 if error else 200,
        context={"page_title": "Đơn hàng", "orders": orders, "error": error,
                 "date_from": date_from, "date_to": date_to,
                 "export_url": "/orders/export.csv?" + urlencode({"from": date_from, "to": date_to})},
    )


# Route CSV đặt trước /orders/{order_id}; UTF-8 BOM giúp Excel đọc tiếng Việt.
@router.get("/orders/export.csv")
def export_orders(date_from: str = Query("", alias="from"), date_to: str = Query("", alias="to")):
    orders = read_orders(date_from=date_from, date_to=date_to)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["id", "customer_email", "status", "created_at"])
    writer.writeheader()
    for order in orders:
        writer.writerow({key: order[key] for key in writer.fieldnames})
    return Response(output.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="orders.csv"'})


# Nạp lựa chọn và giữ lại nội dung form khi người dùng nhập sai.
def render_form(request, error=None, customer_id="", lines=None):
    with get_db() as db:
        customers = [dict(row) for row in db.execute("SELECT * FROM customers ORDER BY id")]
        products = [dict(row) for row in db.execute("SELECT * FROM products ORDER BY sku")]
    return templates.TemplateResponse(
        request=request, name="orders/new.html", status_code=400 if error else 200,
        context={"page_title": "Tạo đơn", "customers": customers, "products": products,
                 "error": error, "selected_customer": str(customer_id),
                 "lines": lines or [{"sku": "", "qty": "1"}]},
    )


# Route cố định /new đặt trước route /{order_id}.
@router.get("/orders/new", response_class=HTMLResponse)
def new_order(request: Request, customer_id: str = ""):
    # Giữ khách được chọn khi đi từ trang chi tiết CRM trong T010.
    return render_form(request, customer_id=customer_id)


# Đọc các dòng SKU/qty lặp lại; chỉ lưu khi toàn bộ dữ liệu hợp lệ.
@router.post("/orders/new")
async def create_order(request: Request):
    form = await request.form()
    customer_id = str(form.get("customer_id", ""))
    skus = form.getlist("sku")
    quantities = form.getlist("qty")
    lines = [{"sku": sku, "qty": qty} for sku, qty in zip(skus, quantities)]
    try:
        if not skus or len(skus) != len(quantities):
            raise ValueError("Cần ít nhất một dòng sản phẩm có số lượng.")
        if len(set(skus)) != len(skus):
            raise ValueError("Mỗi SKU chỉ xuất hiện một lần; hãy gộp số lượng.")
        if not customer_id.isdecimal():
            raise ValueError("Vui lòng chọn khách hàng.")
        parsed_qty = []
        for qty in quantities:
            if not isinstance(qty, str) or not qty.isascii() or not qty.isdecimal() or not 1 <= int(qty) <= 1000000:
                raise ValueError("Số lượng phải là số nguyên từ 1 đến 1000000.")
            parsed_qty.append(int(qty))
        with get_db() as db:
            if not db.execute("SELECT 1 FROM customers WHERE id = ?", (int(customer_id),)).fetchone():
                raise ValueError("Khách hàng không tồn tại.")
            for sku in skus:
                if not isinstance(sku, str) or not db.execute("SELECT 1 FROM products WHERE sku = ?", (sku,)).fetchone():
                    raise ValueError("Sản phẩm không tồn tại.")
            # Đơn và các dòng hàng được commit cùng nhau; lỗi sẽ rollback toàn bộ.
            cursor = db.execute(
                "INSERT INTO orders (customer_id, status, created_at) VALUES (?, 'pending', ?)",
                (int(customer_id), datetime.now(timezone.utc).isoformat()),
            )
            order_id = cursor.lastrowid
            db.executemany("INSERT INTO order_items (order_id, sku, qty) VALUES (?, ?, ?)",
                           [(order_id, sku, qty) for sku, qty in zip(skus, parsed_qty)])
    except ValueError as exc:
        return render_form(request, str(exc), customer_id, lines)
    return RedirectResponse(f"/orders/ORD-{order_id + 1000}", status_code=303)


# Tra cứu mã hiển thị; mã không tồn tại trả 404.
def find_order(order_id: str):
    for order in read_orders():
        if order["id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")


# Mở chi tiết để người dùng đối chiếu khách, sản phẩm và trạng thái.
@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail(request: Request, order_id: str):
    return templates.TemplateResponse(
        request=request, name="orders/detail.html",
        context={"page_title": "Chi tiết đơn hàng", "order": find_order(order_id),
                 "statuses": ORDER_STATUSES, "error": None},
    )


# Chỉ thay trạng thái của đơn được chọn, giữ nguyên khách hàng và sản phẩm.
@router.post("/orders/{order_id}/status")
def update_order_status(request: Request, order_id: str, status: str = Form("")):
    order = find_order(order_id)
    if status not in ORDER_STATUSES:
        return templates.TemplateResponse(
            request=request, name="orders/detail.html", status_code=400,
            context={"page_title": "Chi tiết đơn hàng", "order": order,
                     "statuses": ORDER_STATUSES, "error": "Vui lòng chọn trạng thái hợp lệ."},
        )
    internal_id = int(order["id"][4:]) - 1000
    with get_db() as db:
        cursor = db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, internal_id))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


# API chỉ đọc phục vụ success criteria T004, không tạo đơn thay giao diện.
@router.get("/api/orders")
def get_orders(customer_email: str | None = None, date_from: str = Query("", alias="from"), date_to: str = Query("", alias="to")):
    orders = read_orders(customer_email, date_from, date_to)
    return {"count": len(orders), "orders": orders}


# API chi tiết cho việc đối chiếu một đơn cụ thể.
@router.get("/api/orders/{order_id}")
def get_order(order_id: str):
    return find_order(order_id)
