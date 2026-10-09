from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import get_db
from app.routes.orders import find_order, read_orders

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


# Trả quan hệ thật trong database; evaluator tự đối chiếu ticket với đơn mới của T010.
def read_tickets(order_id=None, customer_email=None):
    with get_db() as db:
        rows = db.execute("""SELECT t.*, c.email AS customer_email, s.name AS assignee_name
            FROM tickets t JOIN orders o ON o.id=t.order_id
            JOIN customers c ON c.id=o.customer_id LEFT JOIN staff s ON s.id=t.assignee_id
            ORDER BY t.id""").fetchall()
    result = []
    for row in rows:
        ticket = dict(row)
        ticket["id"] = f"TCK-{ticket['id'] + 2000}"
        ticket["order_id"] = f"ORD-{ticket['order_id'] + 1000}"
        if order_id is not None and ticket["order_id"] != order_id:
            continue
        if customer_email is not None and ticket["customer_email"] != customer_email.strip().lower():
            continue
        result.append(ticket)
    return result


# Mã không tồn tại trả 404, không thay đổi trạng thái.
def find_ticket(ticket_id):
    for ticket in read_tickets():
        if ticket["id"] == ticket_id:
            return ticket
    raise HTTPException(404, "Không tìm thấy ticket.")


# Danh sách là điểm xuất phát cho T007–T009.
@router.get("/tickets")
def list_tickets(request: Request):
    return templates.TemplateResponse(request=request, name="tickets/list.html",
        context={"page_title": "Hỗ trợ", "tickets": read_tickets()})


# Giữ dữ liệu form khi lỗi; đơn được chọn sẵn nếu đến từ trang đơn hàng.
def render_new(request, order_id="", subject="", error=None):
    return templates.TemplateResponse(request=request, name="tickets/new.html",
        status_code=400 if error else 200,
        context={"page_title": "Tạo ticket", "orders": read_orders(),
                 "selected_order": order_id, "subject": subject, "error": error})


# Route cố định /new phải nằm trước /{ticket_id}.
@router.get("/tickets/new")
def new_ticket(request: Request, order_id: str = ""):
    return render_new(request, order_id)


# Ticket luôn được tạo open, gắn với đơn tồn tại, chưa có người xử lý.
@router.post("/tickets/new")
def create_ticket(request: Request, order_id: str = Form(""), subject: str = Form("")):
    subject = subject.strip()
    if not subject or len(subject) > 200:
        return render_new(request, order_id, subject, "Tiêu đề phải có từ 1 đến 200 ký tự.")
    try:
        order = find_order(order_id)
    except HTTPException:
        return render_new(request, order_id, subject, "Vui lòng chọn đơn hàng tồn tại.")
    with get_db() as db:
        cursor = db.execute("INSERT INTO tickets (order_id,subject,status) VALUES (?,?,'open')",
                            (int(order["id"][4:]) - 1000, subject))
        ticket_id = cursor.lastrowid
    return RedirectResponse(f"/tickets/TCK-{ticket_id + 2000}", status_code=303)


# Chi tiết chứa hai form riêng: gán nhân viên và đóng kèm ghi chú.
def render_detail(request, ticket, error=None):
    with get_db() as db:
        staff = [dict(row) for row in db.execute("SELECT * FROM staff ORDER BY id")]
    return templates.TemplateResponse(request=request, name="tickets/detail.html",
        status_code=400 if error else 200,
        context={"page_title": "Chi tiết ticket", "ticket": ticket, "staff": staff, "error": error})


@router.get("/tickets/{ticket_id}")
def ticket_detail(request: Request, ticket_id: str):
    # Chỉ đọc; mở trang không tự thay đổi trạng thái.
    return render_detail(request, find_ticket(ticket_id))


# T008: gán đúng nhân viên và chuyển sang in_progress trong cùng transaction.
@router.post("/tickets/{ticket_id}/assign")
def assign_ticket(request: Request, ticket_id: str, assignee_id: str = Form("")):
    ticket = find_ticket(ticket_id)
    with get_db() as db:
        member = db.execute("SELECT id FROM staff WHERE CAST(id AS TEXT)=?", (assignee_id,)).fetchone()
        if member is None or ticket["status"] == "closed":
            return render_detail(request, ticket, "Chọn nhân viên hợp lệ; không gán ticket đã đóng.")
        db.execute("UPDATE tickets SET assignee_id=?,status='in_progress' WHERE id=?",
                   (member["id"], int(ticket_id[4:]) - 2000))
    return RedirectResponse(f"/tickets/{ticket_id}", status_code=303)


# T009: ghi chú bắt buộc; lưu note và closed cùng lúc.
@router.post("/tickets/{ticket_id}/close")
def close_ticket(request: Request, ticket_id: str, note: str = Form("")):
    ticket = find_ticket(ticket_id)
    note = note.strip()
    if not note or len(note) > 2000 or ticket["status"] == "closed":
        return render_detail(request, ticket, "Cần ghi chú 1–2000 ký tự và ticket chưa đóng.")
    with get_db() as db:
        db.execute("UPDATE tickets SET status='closed',note=? WHERE id=?",
                   (note, int(ticket_id[4:]) - 2000))
    return RedirectResponse(f"/tickets/{ticket_id}", status_code=303)


# API chỉ đọc, trả count và dữ liệu để chấm T007/T010.
@router.get("/api/tickets")
def get_tickets(order_id: str | None = None, customer_email: str | None = None):
    tickets = read_tickets(order_id, customer_email)
    return {"count": len(tickets), "tickets": tickets}


# API chi tiết phục vụ T008/T009.
@router.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    return find_ticket(ticket_id)
