# Benchmark Specification v0.1

Trạng thái: bản nháp W1, khóa MVP khi kết thúc W1; mọi thay đổi scope ghi qua ADR.

## 1. Mục tiêu
Đo khả năng của các cấu hình tự động hóa (selector truyền thống vs. agent semantic DOM + LLM) trong việc hoàn thành tác vụ nghiệp vụ Web khi DOM/UI thay đổi, và đo khả năng tự phục hồi locator (self-healing).

Câu hỏi nghiên cứu:
- RQ1: Selector truyền thống suy giảm bao nhiêu theo từng loại/mức mutation?
- RQ2: Semantic ranking (không LLM) phục hồi được bao nhiêu phần trăm locator vỡ?
- RQ3: LLM fallback cải thiện bao nhiêu so với semantic-only, đổi lại bằng latency và token cost bao nhiêu?

## 2. Ứng dụng thử nghiệm ("MiniBiz")
Web app tổng hợp do nhóm sở hữu, 3 module:

| Module | Trang chính | Chức năng |
|---|---|---|
| CRM | /customers, /customers/new, /customers/{id} | Danh sách, tìm kiếm, tạo, sửa khách hàng |
| Order | /orders, /orders/new, /orders/{id} | Tạo đơn, đổi trạng thái, lọc theo ngày, xuất CSV |
| Support | /tickets, /tickets/new, /tickets/{id} | Tạo ticket gắn đơn, gán người xử lý, đóng ticket |

Mô hình dữ liệu tối thiểu:
`customers(id, name, email, phone)`, `products(sku, name, price)`, `orders(id, customer_id, status, created_at)`, `order_items(order_id, sku, qty)`, `staff(id, name)`, `tickets(id, order_id, subject, status, assignee_id, note)`.

Trạng thái đơn: `pending`, `confirmed`, `shipped`, `delivered`, `cancelled`.
Trạng thái ticket: `open`, `in_progress`, `closed`.

Mọi trạng thái đều đọc được qua API `GET /api/...` để kiểm tra success criteria (không dựa vào giao diện). Mỗi lần chạy task, DB được reset về `seed_v1` (dữ liệu cố định, có checksum trong manifest).

## 3. Định nghĩa task
Mỗi task có: `goal` (ngôn ngữ tự nhiên), `start_url`, `seed`, `success_criteria` kiểm tra bằng API/DB/download, `max_steps`, `module`, `tags`. Schema: `tasks/task_schema.json`.

Quy tắc viết task:
1. Goal không chứa selector hay chỉ dẫn UI cụ thể (agent chỉ thấy mục tiêu).
2. Success criteria kiểm tra trạng thái cuối, không kiểm tra đường đi.
3. Task phải giải được ở M0 bằng baseline do con người viết trong tối đa `max_steps`.
4. Mỗi task khai báo `critical_elements`: các phần tử mà mutation có thể làm vỡ locator.

Quy mô: pilot 10 task (W1), 20 (W2), 30 x mutation (W4), 40-60 (W8). Độ khó: `single` (một thao tác), `multi` (nhiều bước), `chain` (xuyên module).

## 4. Mutation DOM/UI
Một app duy nhất sinh nhiều phiên bản DOM qua tham số `?mutation=Mx&seed=s`, thực hiện ở lớp template, không viết nhiều app.

| Mức | Loại | Thao tác | Dự kiến vỡ |
|---|---|---|---|
| M0 | Gốc | Không đổi | Không |
| M1 | Thuộc tính | Đổi/randomize `id`, `class`, `name`, `data-*` | CSS theo id/class |
| M2 | Nhãn | Đổi text/label/placeholder ("Lưu" thành "Xác nhận") | Locator theo text |
| M3 | Cấu trúc | Di chuyển node, thêm sibling/wrapper, đổi thứ tự cột | XPath tuyệt đối, nth-child |
| M4 | Layout | Form thành modal, bảng thành card, tab thành accordion | Gần như mọi locator |
| M5 | Kết hợp | Tổ hợp M1-M4 với seed ngẫu nhiên; bộ held-out dùng ở W11 | Test cuối |

MVP khóa ở 3 mức: M1, M2, M3 (cùng M0 làm đối chứng). M4 và M5 là mức mở rộng, chỉ làm khi core metrics đạt. Mỗi mutation phải tái lập được (cùng `mutation` + `seed` cho cùng DOM) và bảo toàn chức năng (cùng success criteria).

Mutation dùng để phát triển (W3-W10) tách hẳn khỏi mutation held-out dùng đánh giá cuối (W11); khai báo trong `data/manifest.json`.

## 5. Các cấu hình đánh giá
Baseline (không LLM):
- **B0**: CSS/XPath viết tay trên DOM M0 (locator tĩnh).
- **B1**: Playwright locator ngữ nghĩa (`get_by_role`, `get_by_label`, `get_by_text`).

Agent (2 configurations theo đề cương; đề xuất, chốt bằng ADR ở W3):
- **A1**: semantic DOM + candidate ranking (attributes/text/structure/embedding), không LLM fallback.
- **A2**: A1 + LLM fallback khi độ tin cậy ranking thấp hoặc hành động thất bại.

Ablation W9: no-LLM / semantic / LLM fallback (tương ứng B1, A1, A2).

## 6. Chỉ số đánh giá
| Chỉ số | Định nghĩa |
|---|---|
| Task success rate | Số lần chạy thỏa success criteria / tổng số lần chạy |
| Self-healing recovery rate | Trong các lần locator gốc thất bại, tỷ lệ agent chọn đúng phần tử và hoàn thành bước |
| Mean steps, retry count | Số hành động trung bình mỗi task; số lần thử lại |
| Latency | Median và p95 thời gian hoàn thành task (giây) |
| Token cost | Tổng token vào/ra và chi phí quy đổi mỗi task |
| Robustness | Success và recovery theo từng loại/mức mutation |

Tái lập: mỗi cấu hình dùng LLM chạy nhiều lần (đề xuất n=3) với seed cố định, nhiệt độ thấp, log JSON trace mỗi lần; báo cáo trung bình, độ lệch chuẩn, khoảng tin cậy bootstrap.

## 7. Giao thức chạy (dự kiến cho harness W8)
1. Reset DB về `seed_v1`.
2. Khởi động app với `mutation=Mx&seed=s`.
3. Chạy cấu hình trên task, ghi trace JSON (bước, locator, ứng viên, điểm, token, thời gian).
4. Gọi `success_criteria` để chấm.
5. Ghi kết quả CSV/JSON vào `runs/<run_id>/`, kèm commit hash và checksum.

## 8. Phạm vi và giới hạn
- Chỉ chạy trên MiniBiz do nhóm sở hữu; không tự động hóa website bên thứ ba.
- Dữ liệu seed hoàn toàn tổng hợp, không dùng dữ liệu cá nhân thật.
- Ngoài phạm vi MVP: CAPTCHA, đăng nhập đa yếu tố, upload file, nhiều tab, iframe lồng nhau.

## 9. Rủi ro chính
| Rủi ro | Giảm thiểu |
|---|---|
| Scope quá rộng | Khóa MVP ở W1; stretch chỉ mở sau khi core metrics đạt |
| API/LLM đắt hoặc không ổn định | Baseline local, cache phản hồi, quota, ghi chi phí |
| Tích hợp muộn | Thin slice end-to-end trước W5-W6 |
| Báo cáo không khớp code | Cập nhật evidence hằng tuần; số liệu truy ngược tới file kết quả/commit |
