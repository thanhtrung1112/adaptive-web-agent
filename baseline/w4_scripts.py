"""M0 scripts for T021-T030 only; reuse W2 locator definitions unchanged."""
from .scripts import goto, click, fill, select, download, find_customer, SKU_100, SKU_205

# Business fixtures for feasibility checks, not adaptive ranking or semantic baseline.
EXTRA_SCRIPTS = {
    'T021': [goto('/customers'),click('btn_add_customer'),fill('cust_name','Công ty An & Bình'),fill('cust_email','anbinh@example.com'),fill('cust_phone','0902223344'),click('btn_save_customer')],
    'T022': [goto('/customers'),*find_customer('nguyen.dung@example.com')],
    'T023': [goto('/customers'),*find_customer('vo.tam@example.com'),click('btn_edit_customer'),fill('cust_phone','0977772233'),click('btn_save_customer')],
    'T024': [goto('/orders'),click('btn_create_order'),select('order_customer','Võ Thanh Tâm — vo.tam@example.com'),select('line_sku',SKU_100,n=1),fill('line_qty','3',n=1),click('btn_add_line'),select('line_sku',SKU_205,n=2),fill('line_qty','2',n=2),click('btn_save_order')],
    'T025': [goto('/orders'),click('order_link',oid='ORD-1001'),select('order_status','Đã hủy'),click('btn_update_status')],
    'T026': [goto('/orders'),fill('filter_from','2026-08-30'),fill('filter_to','2026-08-30'),click('btn_filter'),download('btn_export')],
    'T027': [goto('/tickets'),click('ticket_link',tid='TCK-2001'),fill('ticket_note','Đã xác nhận thông tin đơn'),click('btn_close_ticket')],
    'T028': [goto('/tickets'),click('ticket_link',tid='TCK-2001'),select('ticket_assignee','Nguyễn Mai Lan'),click('btn_assign')],
    'T029': [goto('/tickets'),click('btn_create_ticket'),select('ticket_order','ORD-1004 — nguyen.dung@example.com'),fill('ticket_subject','Cần kiểm tra đóng gói'),click('btn_save_ticket'),fill('ticket_note','Đã kiểm tra đóng gói'),click('btn_close_ticket')],
    'T030': [goto('/customers'),*find_customer('pham.ha@example.com'),click('btn_customer_create_order'),select('line_sku',SKU_205,n=1),fill('line_qty','5',n=1),click('btn_save_order'),click('btn_order_create_ticket'),fill('ticket_subject','Hỏi lịch giao'),click('btn_save_ticket'),select('ticket_assignee','Nguyễn Mai Lan'),click('btn_assign')],
}
