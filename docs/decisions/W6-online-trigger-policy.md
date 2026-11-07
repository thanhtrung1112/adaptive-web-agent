# ADR W6-A — Khi nào gọi healing trong runner online

Trạng thái: triển khai để review; chưa thay cho xác nhận của thành viên còn lại.

## Quyết định

- Runner dùng script B0 viết tay và descriptor đã ghi trên M0, cố định theo task/bước.
- Chỉ gọi `heal()` khi `count()` của locator B0 bằng 0 (`missing`) hoặc lớn hơn 1
  (`multiple`). Một bước có tối đa một lần healing; không lặp mù khi bỏ cuộc.
- Khi B0 khớp đúng một phần tử, thao tác bằng B0. Lỗi visible/enabled/actionability,
  timeout hoặc lỗi thao tác được ghi là thất bại, không tự chuyển sang ứng viên khác.
- Healing dùng `features`, `min_margin=0.02`, `min_score=0.0`, `use_order=True`.
  Đây là cấu hình C đã định trước từ W6 offline, không chọn lại theo kết quả online.
- Chỉ thực thi khi `healed` và XPath mới khớp đúng một phần tử. Khi `abstain`, dừng
  task và ghi lý do; không dùng oracle để cứu task thất bại.
- Mỗi task reset DB tạm và dùng browser context mới. Chấm bằng success criteria
  API/CSV của task; yêu cầu seed chưa thỏa mục tiêu và mọi bước thực thi thành công.
- Không đưa target ID, oracle CSS/ID mapping, quy tắc mutation hoặc success criteria
  vào `heal()`. Giá trị nghiệp vụ trong script B0 được giữ nguyên.

## Chỉ số và giới hạn

`task_recovery_rate` = task có ít nhất một lần gọi healing và cuối cùng đạt API
chia cho tất cả task có gọi healing. Đây là recovery **cấp task**, không phải độ
chính xác chọn phần tử của từng bước. Trace giữ riêng action success, quyết định
healing, điểm và kết quả API. Không có nhãn đích online độc lập thì số chữa nhầm
được ghi `null`, không suy ra bằng 0 từ task pass.

Chính sách này chưa phát hiện `wrong_target` khi B0 khớp một phần tử sai. Không
luôn xác minh descriptor vì đó là một cấu hình khác, có thể đổi tần suất healing
và phạm vi thí nghiệm. Các bước B0 tiếp theo chạy trên trạng thái sau phục hồi;
đếm trigger trong lượt adaptive không thay thế một ma trận B0 độc lập.

## Mutation set

W6-v1 giữ nguyên mã mutation benchmark 0.5.0 nhưng đóng băng **cấu hình phát triển
mới** với seed 17/18, tách manifest `data/w6-mutation-set-v1.json` khỏi W5 17/23.
Không sửa đè bằng chứng W5 hoặc so trực tiếp hai tập seed như cùng một dataset.
Audit các trạng thái M0 trước thao tác, loại URL/hidden field/script query chứa
mutation và seed trước khi so DOM. Đóng băng trước đo online, không xem kết quả
success để chọn seed. Giữ held-out W11 chưa truy cập.
