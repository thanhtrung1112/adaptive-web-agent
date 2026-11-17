# W7 — Phần Trung (resolver, wrong-target guard và demo)

## Phần đã thêm

- `llm/fallback.py`: prompt chống prompt-injection từ DOM, Top-K tối đa 5, ưu tiên thứ tự semantic ranker rồi bổ sung lexical ranking; gọi `client.generate_json()` đúng một lần; chỉ chấp nhận candidate nằm trong Top-K; trả `abstain` nếu không có candidate.
- `w7/target_check.py`: `check_found()` kiểm tra độ tương thích giữa mục tiêu nghiệp vụ và ngữ cảnh DOM. Đây là guard bảo thủ, không phải chứng minh tuyệt đối rằng target đúng.
- `w7/case_audit.py`: hiệu chỉnh threshold từ các cặp candidate đúng/sai được gán nhãn trong bộ DOM dev riêng; ghi `target-threshold.json`. Bộ này không phải held-out và không cộng vào MiniBiz task-success.
- `w7/run_agent.py`: áp dụng guard cho candidate A1/A2 trước thao tác; ghi threshold vào metadata; nhận `--target-threshold` để dùng đúng ngưỡng đã hiệu chỉnh.
- `w7/demo.py`: demo natural language → W3 intent/plan → semantic matcher → LLM fallback khi cần → Playwright thao tác.
- `tests/test_w7_fallback.py`: kiểm tra select, abstain, Top-K, candidate ngoài Top-K và sai ngữ cảnh.

## Chạy trên máy phát triển

Cài đúng dependencies theo `docs/w7-binh-handoff.md`, sau đó cài Chromium:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q tests/test_w7_fallback.py
```

Tạo dev challenge và lấy threshold được hiệu chỉnh:

```powershell
.\.venv\Scripts\python.exe -m w7.case_audit --output runs/w7-cases-dev-v2
Get-Content runs/w7-cases-dev-v2/target-threshold.json
```

Dùng cùng threshold cho A1 và A2. Tạo record W6 mới nếu máy chưa có record hợp manifest:

```powershell
.\.venv\Scripts\python.exe -m w6.run_heal --mode record --output runs/w7-record-v2
.\.venv\Scripts\python.exe -m w7.run_agent --agent b0 --output runs/w7-b0-v2
.\.venv\Scripts\python.exe -m w7.run_agent --agent a1 --record runs/w7-record-v2 --target-threshold <DEV_THRESHOLD> --output runs/w7-a1-v2
.\.venv\Scripts\python.exe -m w7.run_agent --agent a2 --record runs/w7-record-v2 --resolver llm.fallback:resolve --target-threshold <DEV_THRESHOLD> --max-requests 20 --max-output-tokens 512 --max-reserved-output-tokens 10240 --output runs/w7-a2-v2
.\.venv\Scripts\python.exe -m w7.report runs/w7-b0-v2 runs/w7-a1-v2 runs/w7-a2-v2 --output runs/w7-comparison-v2.json
```

Demo tự nhiên (ví dụ nghiệp vụ cập nhật số điện thoại):

```powershell
.\.venv\Scripts\python.exe -m w7.demo --goal "Đổi số điện thoại của hoa@example.com thành 0909998888." --target-threshold <DEV_THRESHOLD> --output runs/w7-natural-demo
```

Cần cấu hình `OPENAI_API_KEY` cục bộ và `OPENAI_MODEL=gpt-4.1-mini`. Không commit `.env`/khóa API.

## Tình trạng xác minh trong môi trường đóng gói

- Unit test fallback: 6/6 đạt.
- `compileall` các module mới và module tích hợp: đạt.
- Browser integration, dev threshold từ DOM thật, demo browser, GPT-4.1 mini live evaluation và B0/A1/A2 benchmark chưa được xác nhận ở môi trường đóng gói: thiếu Chromium và API key. Không coi fake-client test là kết quả GPT thật; không tạo số liệu benchmark giả.
- Khi chạy challenge, threshold ghi trong `target-threshold.json` phải được truyền nguyên giá trị cho cả A1 và A2. Nếu thay đổi code/prompt/cấu hình sau khi khóa, phải chạy lại cả ba nhánh trên cùng source hash.
