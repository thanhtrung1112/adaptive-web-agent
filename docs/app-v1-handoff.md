# Bàn giao MiniBiz Web App v1

## Phạm vi và dữ liệu

Ứng dụng local gồm CRM, Order, Support và luồng liên thông cho pilot T001–T010.
Chỉ dùng dữ liệu tổng hợp trên website nhóm sở hữu. Chưa có xác thực người dùng;
chỉ chạy trên loopback cho benchmark nội bộ. `data/manifest.json` ghi SHA-256 của seed.
Seed và manifest dùng LF theo `.gitattributes`. Khi sửa seed, chạy
`python scripts/seed_manifest.py --update` để chuẩn hóa LF và cập nhật SHA-256
theo byte thực tế; chạy `python scripts/seed_manifest.py` để kiểm tra trước commit.
Seed không có khách Lê Minh Anh, đơn cho
Phạm Thu Hà/Võ Thanh Tâm hoặc ticket cho ORD-1002, để task tạo mới không đạt giả.

## Cách kiểm tra từng task

Trước mỗi task: dừng server, chạy reset theo README, khởi động lại và dùng phiên
trình duyệt mới. Thực hiện nghiệp vụ qua giao diện; API chỉ dùng đối chiếu kết quả.

| Task | Thao tác | Đối chiếu |
|---|---|---|
| T001 | Tạo Lê Minh Anh theo pilot task | `/api/customers?email=minhanh@example.com`, count=1, tên và phone đúng |
| T002 | Tìm Trần Hoa, mở chi tiết | `/api/session/last_viewed_customer`, email đúng; dùng cùng cookie trình duyệt |
| T003 | Sửa phone Nguyễn Văn Dũng | `/api/customers?email=nguyen.dung@example.com`, phone=0987654321 |
| T004 | Tạo đơn cho Phạm Thu Hà với 2 SKU | `/api/orders?customer_email=pham.ha@example.com`, count=1, pending, SKU-100×1 và SKU-205×3 |
| T005 | Mở ORD-1003, chọn Đã giao, Cập nhật | `/api/orders/ORD-1003`, status=delivered |
| T006 | Lọc 01/09–15/09/2026, xuất CSV | IDs CSV và `/api/orders?from=2026-09-01&to=2026-09-15` cùng bằng ORD-1002, ORD-1003, ORD-1004 |
| T007 | Tạo ticket Giao hàng chậm cho ORD-1002 | `/api/tickets?order_id=ORD-1002`, count=1, subject đúng, status=open |
| T008 | Gán TCK-2001 cho Hoàng Quang Huy | `/api/tickets/TCK-2001`, assignee_name đúng, status=in_progress |
| T009 | Đóng TCK-2002, ghi Đã hoàn tiền cho khách | `/api/tickets/TCK-2002`, note đúng, status=closed |
| T010 | Tìm Võ Thanh Tâm → mở chi tiết → Tạo đơn SKU-100×2 → Tạo ticket Hỏi thời gian giao | API orders/tickets lọc customer_email=vo.tam@example.com, mỗi count=1; ticket.order_id bằng order.id mới |

T006 dùng ngày UTC, bao gồm hai đầu mút. CSV UTF-8 BOM có các cột id,
customer_email, status, created_at. Không có kết quả thì CSV chỉ có dòng tiêu đề.
Nhấn Lọc trước khi Xuất CSV; liên kết tải mang khoảng ngày đã áp dụng.

## Hợp đồng API cho người viết baseline

API danh sách trả `count` và mảng `customers`, `orders` hoặc `tickets`.
API chi tiết trả object trực tiếp. `expect.fields` của task được đối chiếu với
object chi tiết hoặc phần tử của mảng kết quả (khi count=1).
`expect.items` kiểm tra SKU/qty chính xác trong đơn, không chỉ số lượng dòng.
`linked_to_new_order` là điều kiện evaluator phải kiểm tra bằng quan hệ ID;
không phải cờ thành công do app cung cấp. API chấm T002 không tự ghi nhận lượt xem.
Không dùng HTTP client mất cookie của trình duyệt để chấm T002.

Chạy từng task tuần tự, reset trước mỗi task; database dùng chung không hỗ trợ
reset đồng thời giữa nhiều lượt chạy. Phiên local hết hiệu lực khi server restart.
App chỉ có một tiến trình Uvicorn; baseline phải cố định phiên bản mã và seed.

## Kiểm thử và giới hạn

Các test trong `tests/` kiểm tra HTTP, template, database, CSV và quan hệ dữ liệu.
Chúng chưa thay thế kiểm thử thao tác thực tế trên trình duyệt, đặc biệt JavaScript
Thêm dòng của form đơn hàng. Cần chạy baseline CSS/XPath riêng cho kết quả W2.
Các dependency trong requirements chưa khóa phiên bản; lưu môi trường đã kiểm chứng
trước khi chốt bộ benchmark chính thức.
