"""Baseline B0 cho MiniBiz v1: script locator viết tay cho T001-T010 trên DOM gốc (M0).

Mỗi bước có hai bản locator tương đương:
  - css:   dựa trên id / name / thuộc tính href (cách viết điển hình của dev)
  - xpath: dựa trên text hiển thị, label và quan hệ cấu trúc (cách viết điển hình của tester)
Locator KHÔNG tự sửa: khi DOM đổi mà selector không còn khớp thì bước đó thất bại, đó là điều baseline cần đo.
"""

# key: (css, xpath). {x} là tham số điền theo task.
S = {
    # khách hàng
    "customer_search": ("#customer-search", "//label[normalize-space()='Tìm khách hàng theo email']/following-sibling::input[1]"),
    "btn_search": ("#search-customers", "//button[normalize-space()='Tìm']"),
    "btn_add_customer": ("#add-customer", "//a[normalize-space()='Thêm khách hàng']"),
    "customer_result": ("table a[href^='/customers/']", "//table//tr[td[normalize-space()='{email}']]//a"),
    "cust_name": ("#customer-name", "//label[normalize-space()='Tên khách hàng']/following-sibling::input[1]"),
    "cust_email": ("#customer-email", "//label[normalize-space()='Email']/following-sibling::input[1]"),
    "cust_phone": ("#customer-phone", "//label[normalize-space()='Số điện thoại']/following-sibling::input[1]"),
    "btn_save_customer": ("#save-customer", "//button[normalize-space()='Lưu']"),
    "btn_edit_customer": ("#edit-customer", "//a[normalize-space()='Sửa']"),
    "btn_customer_create_order": ("#customer-create-order", "//a[normalize-space()='Tạo đơn']"),
    # đơn hàng
    "filter_from": ("#orders-from", "//label[normalize-space()='Từ ngày (UTC)']/following-sibling::input[1]"),
    "filter_to": ("#orders-to", "//label[normalize-space()='Đến ngày (UTC)']/following-sibling::input[1]"),
    "btn_filter": ("#filter-orders", "//button[normalize-space()='Lọc']"),
    "btn_export": ("#export-orders", "//a[normalize-space()='Xuất CSV']"),
    "btn_create_order": ("#create-order", "//a[normalize-space()='Tạo đơn']"),
    "order_link": ("table a[href='/orders/{oid}']", "//table//a[normalize-space()='{oid}']"),
    "order_customer": ("#order-customer", "//label[normalize-space()='Khách hàng']/following-sibling::select[1]"),
    "line_sku": ("#order-sku-{n}", "(//select[@name='sku'])[{n}]"),
    "line_qty": ("#order-qty-{n}", "(//input[@name='qty'])[{n}]"),
    "btn_add_line": ("#add-order-line", "//button[normalize-space()='Thêm dòng']"),
    "btn_save_order": ("#save-order", "//button[normalize-space()='Xác nhận tạo đơn']"),
    "order_status": ("#order-status", "//label[normalize-space()='Trạng thái đơn hàng']/following-sibling::select[1]"),
    "btn_update_status": ("#update-order-status", "//button[normalize-space()='Cập nhật']"),
    "btn_order_create_ticket": ("#order-create-ticket", "//a[normalize-space()='Tạo ticket']"),
    # ticket
    "btn_create_ticket": ("#create-ticket", "//a[normalize-space()='Tạo ticket']"),
    "ticket_link": ("table a[href='/tickets/{tid}']", "//table//a[normalize-space()='{tid}']"),
    "ticket_order": ("#ticket-order", "//label[normalize-space()='Đơn hàng']/following-sibling::select[1]"),
    "ticket_subject": ("#ticket-subject", "//label[normalize-space()='Tiêu đề']/following-sibling::input[1]"),
    "btn_save_ticket": ("#save-ticket", "//button[normalize-space()='Gửi']"),
    "ticket_assignee": ("#ticket-assignee", "//label[normalize-space()='Người xử lý']/following-sibling::select[1]"),
    "btn_assign": ("#assign-ticket", "//button[normalize-space()='Gán']"),
    "ticket_note": ("#ticket-note", "//label[normalize-space()='Ghi chú']/following-sibling::textarea[1]"),
    "btn_close_ticket": ("#close-ticket", "//button[normalize-space()='Đóng ticket']"),
}


def _step(do, key=None, **kw):
    step = {"do": do, **kw}
    if key:
        css, xp = S[key]
        step["css"], step["xpath"] = css.format(**kw), xp.format(**kw)
    return step


def goto(url): return {"do": "goto", "url": url}
def click(key, **kw): return _step("click", key, **kw)
def fill(key, value, **kw): return _step("fill", key, value=value, **kw)
def select(key, label, **kw): return _step("select", key, label=label, **kw)
def download(key, **kw): return _step("download", key, **kw)


def find_customer(email):
    """Tìm theo email đầy đủ (app chỉ hỗ trợ tìm theo email) rồi mở trang chi tiết."""
    return [fill("customer_search", email), click("btn_search"), click("customer_result", email=email)]


SKU_100, SKU_205 = "SKU-100 — Bàn phím", "SKU-205 — Chuột máy tính"

SCRIPTS = {
    "T001": [goto("/customers"), click("btn_add_customer"), fill("cust_name", "Lê Minh Anh"),
             fill("cust_email", "minhanh@example.com"), fill("cust_phone", "0901234567"), click("btn_save_customer")],
    "T002": [goto("/customers"), *find_customer("tran.hoa@example.com")],
    "T003": [goto("/customers"), *find_customer("nguyen.dung@example.com"), click("btn_edit_customer"),
             fill("cust_phone", "0987654321"), click("btn_save_customer")],
    "T004": [goto("/orders"), click("btn_create_order"), select("order_customer", "Phạm Thu Hà — pham.ha@example.com"),
             select("line_sku", SKU_100, n=1), fill("line_qty", "1", n=1), click("btn_add_line"),
             select("line_sku", SKU_205, n=2), fill("line_qty", "3", n=2), click("btn_save_order")],
    "T005": [goto("/orders"), click("order_link", oid="ORD-1003"), select("order_status", "Đã giao"),
             click("btn_update_status")],
    "T006": [goto("/orders"), fill("filter_from", "2026-09-01"), fill("filter_to", "2026-09-15"),
             click("btn_filter"), download("btn_export")],
    "T007": [goto("/tickets"), click("btn_create_ticket"), select("ticket_order", "ORD-1002 — nguyen.dung@example.com"),
             fill("ticket_subject", "Giao hàng chậm"), click("btn_save_ticket")],
    "T008": [goto("/tickets"), click("ticket_link", tid="TCK-2001"), select("ticket_assignee", "Hoàng Quang Huy"),
             click("btn_assign")],
    "T009": [goto("/tickets"), click("ticket_link", tid="TCK-2002"), fill("ticket_note", "Đã hoàn tiền cho khách"),
             click("btn_close_ticket")],
    "T010": [goto("/customers"), *find_customer("vo.tam@example.com"), click("btn_customer_create_order"),
             select("line_sku", SKU_100, n=1), fill("line_qty", "2", n=1), click("btn_save_order"),
             click("btn_order_create_ticket"), fill("ticket_subject", "Hỏi thời gian giao"), click("btn_save_ticket")],
}

# W2 mở rộng mục tiêu nghiệp vụ trong cùng MVP, không sửa 10 pilot task W1.
SCRIPTS.update({
    "T011": [goto("/customers"), click("btn_add_customer"), fill("cust_name", "Công ty Sao Mai"),
             fill("cust_email", "saomai@example.com"), fill("cust_phone", "0901112233"), click("btn_save_customer")],
    "T012": [goto("/customers"), *find_customer("pham.ha@example.com")],
    "T013": [goto("/customers"), *find_customer("tran.hoa@example.com"), click("btn_edit_customer"),
             fill("cust_phone", "0912345678"), click("btn_save_customer")],
    "T014": [goto("/orders"), click("btn_create_order"), select("order_customer", "Phạm Thu Hà — pham.ha@example.com"),
             select("line_sku", SKU_205, n=1), fill("line_qty", "4", n=1), click("btn_save_order")],
    "T015": [goto("/orders"), click("order_link", oid="ORD-1002"), select("order_status", "Đã xác nhận"), click("btn_update_status")],
    "T016": [goto("/orders"), click("order_link", oid="ORD-1004"), select("order_status", "Đang giao"), click("btn_update_status")],
    "T017": [goto("/orders"), click("order_link", oid="ORD-1005"), select("order_status", "Đã hủy"), click("btn_update_status")],
    "T018": [goto("/orders"), fill("filter_from", "2026-09-16"), fill("filter_to", "2026-09-16"), click("btn_filter"), download("btn_export")],
    "T019": [goto("/tickets"), click("ticket_link", tid="TCK-2002"), select("ticket_assignee", "Hoàng Quang Huy"), click("btn_assign")],
    "T020": [goto("/tickets"), click("btn_create_ticket"), select("ticket_order", "ORD-1005 — tran.hoa@example.com"),
             fill("ticket_subject", "Cần xác nhận địa chỉ"), click("btn_save_ticket"),
             select("ticket_assignee", "Hoàng Quang Huy"), click("btn_assign")],
})
