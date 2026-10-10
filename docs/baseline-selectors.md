# Baseline CSS và XPath W2

## Phạm vi
20 task khác nhau trong `tasks/tasks_w2.json`: 6 CRM, 8 Order, 5 Support, 1 chain.
10 pilot task W1 giữ nguyên trong `tasks/pilot_tasks.json`. T011–T020 mở rộng mục tiêu
và dữ liệu trong chức năng hiện có; không coi đây là 20 loại workflow hoàn toàn khác nhau.
Mỗi bước có CSS/XPath viết tay trên M0, không tự phục hồi, không retry, không LLM.

## Cài và chạy từ repo
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/validate_tasks.py tasks/tasks_w2.json
.\.venv\Scripts\python.exe -m baseline.run_baseline --mode both
```
Không cần mở Uvicorn trước. Runner tự khởi động server trên cổng local rảnh và database
SQLite tạm; server và runner dùng cùng MINIBIZ_DB_PATH. App người dùng trên cổng 8000
không bị reset. Chạy task tuần tự, reset seed và browser context mới trước mỗi task.
Ví dụ kiểm tra riêng: thêm `--tasks T002 T006 T010`. ID sai bị từ chối.

## Giao thức và cách chấm
- Timeout mỗi hành động: 5 giây; max_steps theo từng task; không retry.
- Một goto/fill/select/click/download tính một bước. API chấm không tính vào bước.
- Latency đo từ hành động đầu đến hành động cuối, gồm tải trang/CSV; không gồm
  reset, tạo context hoặc API chấm. p95 dùng nearest-rank trên toàn bộ task.
- API chấm T002 dùng cùng cookie; T010 đối chiếu ticket.order_id với đơn mới.
- CSV phải có header mã đơn và đúng số lần xuất hiện của từng ID (không chấp nhận lặp dòng).
- Giá trị 100% trên M0 không chứng minh khả năng thích nghi mutation.
- Mỗi cấu hình chạy một lần/task. Chưa có ước lượng độ biến thiên hoặc ý nghĩa thống kê.

## Kết quả đã lưu
| Cấu hình | Thành công | Median (s) | p95 (s) | Bước trung bình |
|---|---|---|---|---|
| CSS | 20/20 | 0.1858 | 0.3309 | 5.5 |
| XPath | 20/20 | 0.1906 | 0.3217 | 5.5 |

Nguồn: `results/w2/baseline_M0_results.csv` và `baseline_M0_summary.json`.
Metadata ghi commit nền, trạng thái chưa commit lúc chạy, hash LF từng tệp nguồn,
hash seed/task, Python, thư viện và Chromium. Vì có chỉnh sửa chưa commit, không được
coi commit nền một mình là phiên bản đã đo; đối chiếu thêm source_hashes_lf.
Trace từng bước và CSV tải về nằm cùng thư mục kết quả. Kết quả pilot 10 task cũ
được giữ ở `results/w2/pilot_10_tasks/`, không trộn vào kết quả 20 task.

## Bằng chứng nộp
Repo lưu mã nguồn, task, CSV/JSON kết quả, trace và báo cáo. Không lưu demo/video
trong repo. Link demo hoặc video cho LMS sẽ bổ sung riêng khi nhóm chuẩn bị nộp.

## Giới hạn
Chỉ M0, Chromium, website local và dữ liệu tổng hợp. Chưa B1 semantic locator,
mutation, LLM hoặc self-healing. Phần này đáp ứng baseline W2, không thay thế harness W8.
