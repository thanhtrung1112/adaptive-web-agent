# Tuần 8 — Bàn giao bộ tác vụ, chấm kết quả và replay

Phần Bình chuẩn bị bộ **40 tác vụ phát triển trên MiniBiz**, chuẩn trace và runner. Tập W8 giữ nguyên 30 mục W4 và thêm T031–T040. Tập mới có 11 tác vụ CRM, 14 Order, 11 Support và 4 luồng liên mô-đun. Các ca bổ sung kiểm tra cả sai bản ghi, nhiều lần cập nhật, biên ngày UTC, CSV và liên kết giữa khách, đơn vừa tạo và ticket.

## Chạy lại

Chạy tại thư mục gốc repo trong môi trường đã cài `requirements-lock.txt` và Chromium của Playwright. Giữ `--output` là thư mục mới cho từng lượt.

```powershell
.\.venv\Scripts\python.exe scripts/validate_tasks.py tasks/tasks_w8.json
.\.venv\Scripts\python.exe -m w8.run record --tasks T003 T006 --output runs/w8-sample
.\.venv\Scripts\python.exe -m w8.run replay --trace runs/w8-sample/traces/T003.json --output runs/w8-replay-t003
.\.venv\Scripts\python.exe -m w8.run replay --trace runs/w8-sample/traces/T006.json --output runs/w8-replay-t006
.\.venv\Scripts\python.exe -m w8.run record --output runs/w8-m0-all
```

Lệnh `record` chạy kịch bản B0 viết tay. Mặc định dùng CSS và M0. Có thể chọn `--locator xpath`, `--mutation W5_ID --seed 17` hoặc một biến đổi đã có của MiniBiz. Mỗi tác vụ dùng database đã reset về `seed_v1` và browser context mới. Run tạo metadata, bảng `results.csv`, `summary.json` và một trace JSON cho từng tác vụ. Tệp CSV tải từ trình duyệt nằm ở `downloads/` của cùng run.

## Giao diện Trung nhận

Tích hợp adapter của Trung làm callback `producer(session, task)` cho `w8.harness.run_case`. Callback nhận `id`, `goal`, `start_url`, `max_steps` và có thể đọc DOM qua `session.page`. Bộ chấm giữ riêng tiêu chí API/CSV. Các thao tác thực thi đi qua `session.act` để mỗi bước có thể replay.

```python
session.act({"action": "navigate", "url": task["start_url"]})
session.act(
    {"action": "fill", "locator": {"strategy": "css", "value": "#customer-search"},
     "value": "nguyen.dung@example.com"},
    decision={"source": "semantic", "reason": "selected the email search control"},
)
```

Selector trong ví dụ minh họa đầu ra sau khi chọn phần tử. Adapter thực tế ghi CSS hoặc XPath đã phân giải từ DOM hiện tại. Các action gồm `navigate` với URL tương đối, `click`, `fill` với `value`, `select` với `label` hoặc `value`, và `download`. `decision` là trường tùy chọn để lưu ứng viên, điểm, lý do fallback hoặc token do agent thực sự ghi nhận. Tham chiếu như *đơn vừa tạo* được Trung phân giải từ trình duyệt trước khi ghi giá trị thao tác cuối cùng vào trace.

## Điều kiện replay

- Runner đối chiếu phiên bản trace, hash tác vụ, seed dữ liệu, mutation, mã app và bộ chấm. Replay chỉ nhận trace thành công.
- Trước mỗi thao tác, runner xác nhận URL và dấu hiệu nhận diện phần tử trùng với lượt gốc. Selector phải khớp duy nhất một phần tử. Sau thao tác, URL phải khớp checkpoint đã lưu. Replay đọc các thao tác đã lưu, với **0 lượt gọi LLM**.
- Bộ chấm dùng API thật của browser context và kiểm tra CSV bằng nội dung tải lại. Kết quả phải khớp quan sát gốc. So sánh bỏ qua thời điểm tạo đơn do đồng hồ sinh lúc chạy. Thời lượng và cổng localhost phục vụ ghi nhận môi trường, không tham gia so sánh.

Mốc bàn giao của Bình là ca `T003` cập nhật số điện thoại và replay lại đúng kết quả API sau khi reset. Phần Trung nối agent vào giao diện này, sau đó hai phần được ghép trên `T003`, `T004`, `T007` và `T010`. Số liệu B0 dùng để kiểm tra khả năng giải và bộ chấm của tập tác vụ.
