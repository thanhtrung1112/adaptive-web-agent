# W8 — Tích hợp Agent W7 vào harness của Bình

## Phạm vi

`w8.agent.producer(session, task)` là adapter giữa Agent W7 và `w8.harness.run_case`.
Adapter giữ nguyên ranh giới thực thi của W8: mọi thao tác trình duyệt (navigate,
click, fill, select, download) phải đi qua `session.act`. Agent chỉ phân tích goal,
lập kế hoạch, đọc DOM hiện tại, chọn XPath duy nhất và chuyển thao tác đã phân giải
cho harness.

Bộ chấm API/CSV, reset dữ liệu, trace schema và replay của Bình không bị thay thế.
Replay vẫn đọc các thao tác đã ghi và không gọi planner/resolver.

## Chạy kiểm thử

Tại thư mục gốc repository, trong môi trường đã cài `requirements-lock.txt`,
Chromium của Playwright và cấu hình `OPENAI_API_KEY` trong `.env`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-w7.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m py_compile w8/agent.py w8/run.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_w8_agent.py
.\.venv\Scripts\python.exe scripts/validate_tasks.py tasks/tasks_w8.json

# B0 đối chứng theo đúng quy trình bàn giao
.\.venv\Scripts\python.exe -m w8.run record --tasks T003 T006 --output runs/w8-sample

# Agent W7 — bốn mốc tích hợp
.\.venv\Scripts\python.exe -m w8.run record --agent w7 --tasks T003 T004 T007 T010 --output runs/w8-agent-m0

# Replay trace Agent; replay không gọi LLM
.\.venv\Scripts\python.exe -m w8.run replay --trace runs/w8-agent-m0/traces/T003.json --output runs/w8-agent-replay-t003
.\.venv\Scripts\python.exe -m w8.run replay --trace runs/w8-agent-m0/traces/T004.json --output runs/w8-agent-replay-t004
.\.venv\Scripts\python.exe -m w8.run replay --trace runs/w8-agent-m0/traces/T007.json --output runs/w8-agent-replay-t007
.\.venv\Scripts\python.exe -m w8.run replay --trace runs/w8-agent-m0/traces/T010.json --output runs/w8-agent-replay-t010
```

Mỗi `--output` phải là thư mục mới. Lệnh Agent ghi audit LLM tại
`runs/w8-agent-m0/llm-calls/`; không đưa API key vào trace hoặc commit.

## Giới hạn hiện tại

Workflow W7 hiện có các nghiệp vụ `find_customer`, `update_phone`,
`create_order`, `create_ticket`, `create_customer` và `close_ticket`.
Vì vậy, adapter này nhắm đến các mốc T003, T004, T007 và T010 mà handoff yêu cầu
ghép. Không coi đây là tuyên bố Agent đã giải được toàn bộ 40 tác vụ W8.

T010 chỉ bind `$last_order` sau khi quan sát URL trang kết quả `/orders/ORD-...`;
không dự đoán mã đơn. Khi chọn dropdown, adapter tìm đúng option theo value/label
hoặc phần mã nghiệp vụ trong label, sau đó ghi label đầy đủ vào action để harness
thực thi ổn định.

## Trạng thái xác minh trên môi trường phát triển

### Kiểm tra mã nguồn và unit test

- Biên dịch bằng `py_compile`: đạt.
- Import W7 planner adapter: đạt.
- `CONTROL_HINTS`: 21 mục.
- `tests/test_w8_agent.py`: 4/4 tests passed.
- Regression:
  - `tests/test_w7.py`
  - `tests/test_w7_fallback.py`
  - `tests/test_w8.py`
  - `tests/test_w8_agent.py`
  - Kết quả: 39/39 tests passed.

### Browser end-to-end

Chạy W8 với W7 Agent trên bốn tác vụ:

| Task | Kết quả |
|---|---|
| T003 | PASS |
| T004 | PASS |
| T007 | PASS |
| T010 | PASS |

Kết quả: 4/4 tác vụ PASS.

### Replay trace

Replay trace của cả bốn tác vụ:

| Task | Kết quả | Steps | Replay match |
|---|---|---:|---|
| T003 | PASS | 7 | True |
| T004 | PASS | 8 | True |
| T007 | PASS | 4 | True |
| T010 | PASS | 13 | True |

Kết quả: 4/4 replay PASS, tổng cộng 32 steps.
Tất cả replay đều có `replay_matches=True`.

### Kết luận

W8 Agent integration đã vượt qua unit test, regression test,
browser end-to-end và replay trên bốn tác vụ T003, T004, T007, T010.

Các kết quả trên được ghi nhận trong môi trường phát triển hiện tại.
