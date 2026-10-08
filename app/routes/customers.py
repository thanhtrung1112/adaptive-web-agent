import sqlite3
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import get_db


router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@router.get("/customers", response_class=HTMLResponse)
def list_customers(request: Request, email: str = ""):
    email = email.strip().lower()
    with get_db() as db:
        if email:
            rows = db.execute(
                "SELECT id, name, email, phone FROM customers WHERE email = ? ORDER BY id",
                (email,),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, name, email, phone FROM customers ORDER BY id"
            ).fetchall()

    return templates.TemplateResponse(
        request=request,
        name="customers/list.html",
        context={
            "page_title": "Khách hàng",
            "customers": [dict(row) for row in rows],
            "email": email,
        },
    )


@router.get("/customers/new", response_class=HTMLResponse)
def new_customer(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="customers/new.html",
        context={
            "page_title": "Thêm khách hàng",
            "error": None,
            "values": {},
        },
    )


@router.post("/customers/new")
def create_customer(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
):
    values = {
        "name": name.strip(),
        "email": email.strip().lower(),
        "phone": phone.strip(),
    }

    error = None

    if not all(values.values()):
        error = "Vui lòng nhập đầy đủ thông tin."
    else:
        try:
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO customers (name, email, phone)
                    VALUES (?, ?, ?)
                    """,
                    (
                        values["name"],
                        values["email"],
                        values["phone"],
                    ),
                )
        except sqlite3.IntegrityError:
            error = "Email này đã tồn tại."

    if error:
        return templates.TemplateResponse(
            request=request,
            name="customers/new.html",
            context={
                "page_title": "Thêm khách hàng",
                "error": error,
                "values": values,
            },
            status_code=400,
        )

    return RedirectResponse(url="/customers", status_code=303)


# Đặt route có ID sau /customers/new để 'new' không bị đọc thành ID.
@router.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail(request: Request, customer_id: int):
    with get_db() as db:
        row = db.execute(
            "SELECT id, name, email, phone FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng.")

    response = templates.TemplateResponse(
        request=request,
        name="customers/detail.html",
        context={"page_title": "Chi tiết khách hàng", "customer": dict(row)},
    )
    request.session["last_viewed_customer_id"] = customer_id
    return response


@router.get("/customers/{customer_id}/edit", response_class=HTMLResponse)
def edit_customer(request: Request, customer_id: int):
    with get_db() as db:
        row = db.execute(
            "SELECT id, name, email, phone FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng.")
    return templates.TemplateResponse(
        request=request,
        name="customers/edit.html",
        context={"page_title": "Sửa khách hàng", "customer": dict(row), "error": None},
    )


@router.post("/customers/{customer_id}/edit")
def update_customer(request: Request, customer_id: int, phone: str = Form("")):
    phone = phone.strip()
    with get_db() as db:
        row = db.execute(
            "SELECT id, name, email, phone FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng.")
        if not phone:
            return templates.TemplateResponse(
                request=request,
                name="customers/edit.html",
                context={
                    "page_title": "Sửa khách hàng",
                    "customer": {**dict(row), "phone": phone},
                    "error": "Vui lòng nhập số điện thoại.",
                },
                status_code=400,
            )
        db.execute("UPDATE customers SET phone = ? WHERE id = ?", (phone, customer_id))
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@router.get("/api/session/last_viewed_customer")
def last_viewed_customer(request: Request):
    customer_id = request.session.get("last_viewed_customer_id")
    if customer_id is None:
        return {"viewed": False, "id": None, "email": None}
    with get_db() as db:
        row = db.execute(
            "SELECT id, name, email, phone FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
    if row is None:
        return {"viewed": False, "id": None, "email": None}
    # Chỉ đọc: API chấm điểm không được tự ghi nhận lượt xem.
    return {"viewed": True, **dict(row)}


@router.get("/api/customers")
def get_customers(email: str | None = None):
    with get_db() as db:
        if email is None:
            rows = db.execute(
                "SELECT id, name, email, phone FROM customers ORDER BY id"
            ).fetchall()
        else:
            rows = db.execute(
                """
                SELECT id, name, email, phone
                FROM customers
                WHERE email = ?
                """,
                (email.strip().lower(),),
            ).fetchall()

    customers = [dict(row) for row in rows]

    return {
        "count": len(customers),
        "customers": customers,
    }
