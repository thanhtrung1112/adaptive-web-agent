"""Handwritten M0 reference scripts, kept separate from the agent's inputs."""

from baseline.run_baseline import SCRIPTS
from baseline.scripts import SKU_100, SKU_205, click, download, fill, find_customer, goto, select


REFERENCE_SCRIPTS = {
    **SCRIPTS,
    "T031": [goto("/customers"), click("btn_add_customer"), fill("cust_name", "Công ty Hồ Sen"),
             fill("cust_email", "holotus@example.com"), fill("cust_phone", "0911300031"),
             click("btn_save_customer"), *find_customer("holotus@example.com")],
    "T032": [goto("/customers"), *find_customer("pham.ha@example.com"), click("btn_edit_customer"),
             fill("cust_phone", "0911300032"), click("btn_save_customer")],
    "T033": [goto("/orders"), click("order_link", oid="ORD-1002"), select("order_status", "Đã xác nhận"),
             click("btn_update_status"), goto("/orders"), click("order_link", oid="ORD-1004"),
             select("order_status", "Đang giao"), click("btn_update_status")],
    "T034": [goto("/orders"), fill("filter_from", "2026-08-31"), fill("filter_to", "2026-08-31"),
             click("btn_filter"), download("btn_export")],
    "T035": [goto("/orders"), click("btn_create_order"), select("order_customer", "Phạm Thu Hà — pham.ha@example.com"),
             select("line_sku", SKU_205, n=1), fill("line_qty", "2", n=1), click("btn_add_line"),
             select("line_sku", SKU_100, n=2), fill("line_qty", "1", n=2), click("btn_save_order"),
             select("order_status", "Đã xác nhận"), click("btn_update_status")],
    "T036": [goto("/tickets"), click("ticket_link", tid="TCK-2001"), select("ticket_assignee", "Nguyễn Mai Lan"),
             click("btn_assign"), goto("/tickets"), click("ticket_link", tid="TCK-2002"),
             select("ticket_assignee", "Hoàng Quang Huy"), click("btn_assign")],
    "T037": [goto("/tickets"), click("btn_create_ticket"), select("ticket_order", "ORD-1002 — nguyen.dung@example.com"),
             fill("ticket_subject", "Đổi địa chỉ nhận hàng"), click("btn_save_ticket"),
             select("ticket_assignee", "Hoàng Quang Huy"), click("btn_assign"),
             fill("ticket_note", "Đã xác nhận địa chỉ mới"), click("btn_close_ticket")],
    "T038": [goto("/tickets"), click("ticket_link", tid="TCK-2002"),
             fill("ticket_note", "Đã đối chiếu A & B, khách xác nhận."), click("btn_close_ticket")],
    "T039": [goto("/customers"), click("btn_add_customer"), fill("cust_name", "Trần Minh Tú"),
             fill("cust_email", "minh.tu.w8@example.com"), fill("cust_phone", "0911300039"),
             click("btn_save_customer"), *find_customer("minh.tu.w8@example.com"), click("btn_customer_create_order"),
             select("line_sku", SKU_205, n=1), fill("line_qty", "2", n=1), click("btn_save_order"),
             click("btn_order_create_ticket"), fill("ticket_subject", "Xác nhận đơn đầu tiên"), click("btn_save_ticket")],
    "T040": [goto("/customers"), *find_customer("vo.tam@example.com"), click("btn_edit_customer"),
             fill("cust_phone", "0911300040"), click("btn_save_customer"), click("btn_customer_create_order"),
             select("line_sku", SKU_100, n=1), fill("line_qty", "3", n=1), click("btn_save_order"),
             click("btn_order_create_ticket"), fill("ticket_subject", "Gọi trước khi giao"), click("btn_save_ticket"),
             select("ticket_assignee", "Nguyễn Mai Lan"), click("btn_assign")],
}
