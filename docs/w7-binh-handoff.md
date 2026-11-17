# W7 — Bàn giao phần Bình cho Trung

Model thống nhất: **GPT-4.1 mini qua OpenAI API**. Phần này chuẩn bị hạ tầng trước; Trung tiếp tục chính sách chọn phần tử. Mã W6 và manifest W6-v1 được giữ nguyên; không chạy lại freeze chỉ để thêm module W7.

Cập nhật dotenv v1.1: client đã tự đọc `.env` và smoke API thật đã trả `API smoke: passed`. Bằng chứng mới ở `Evidence/W07/dotenv-v1.1/`. Đây là kiểm tra kết nối và Structured Outputs, chưa phải benchmark chất lượng A2.

## Đã có trong phần Bình

- `llm/client.py`: OpenAI SDK, Responses API, Structured Outputs, model mặc định `gpt-4.1-mini`, đọc `OPENAI_API_KEY` từ môi trường hoặc `.env` ở gốc repo. Biến môi trường đã đặt có ưu tiên cao hơn `.env`; không ghi khóa vào metadata.
- Retry SDK = 0, timeout hữu hạn, giới hạn request cả lượt và output token đặt trước. Request lỗi cũng tiêu ngân sách. `CallScope` giới hạn mỗi bước tối đa hai request (quyết định + sửa hợp đồng), không có retry thao tác UI.
- Nhật ký API giữ requested/returned model, request/response ID, hash prompt/schema, usage, output JSON và thời gian. Lỗi không chép HTTP body/header vào trace. Usage không biết giữ null; giá tiền không được bịa.
- `w7/run_agent.py`: B0-only, A1 và hook A2; record dùng lệnh W6 hiện có. A2 không chạy nếu chưa truyền resolver của Trung.
- `w7/contracts.py`: packet runtime không chứa XPath/ground truth; mã `c1`, `c2` ánh xạ riêng sang XPath. Kiểm decision/select/abstain và candidate membership trước khi chạy. Candidate thêm context text từ container DOM hiện tại, không đổi công thức ranker W6.
- Executor từ chối DOM đổi sau khi quyết định, XPath không duy nhất, phần tử hidden/disabled, hoặc ô fill không editable. Bước lỗi vẫn có trace/snapshot.
- `w7/plan.py` dùng OpenAI để trích intent theo hợp đồng W3, giữ validator/source span rồi compile workflow. `w7/planner_adapter.py` xuất target ngữ nghĩa và đòi binding runtime có thật. Chưa phải executor hoàn chỉnh cho yêu cầu tự nhiên.
- `w7/case_audit.py`: tạo bộ DOM khó riêng và audit trigger. `w7/challenge_eval.py`: chạy resolver trên packet, chấm nhãn ở sidecar riêng; không gửi đáp án cho model.
- `w7/report.py`: so các lượt có cùng nguồn/manifest/task/mode/seed/locator và chính sách semantic; chỉ nhận lượt đủ coverage. Có tính chi phí từ rate card theo ngày, tách cached input; usage thiếu thì chi phí null.

## Cài đặt

Chạy tại thư mục gốc repo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt -r requirements-w7.txt numpy==2.5.4
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m llm.smoke
```

Lệnh smoke mặc định chỉ in cấu hình, không gọi mạng. NumPy được chỉ rõ vì requirements-lock W6 chưa khai báo gói ranking này; không cần cài SentenceTransformers cho phần W7. `.env.example` là mẫu: tạo `.env` cùng cấp `requirements-w7.txt`, điền khóa cục bộ và model; chương trình tự nạp file này, kể cả khi gọi từ thư mục khác. Không tìm `.env` ở thư mục cha. Biến môi trường đã đặt vẫn được ưu tiên, kể cả chuỗi rỗng. Không gửi khóa vào chat hoặc commit. `.gitignore` bỏ qua `.env`/`.env.*`, trừ mẫu `.env.example`.

Bản sửa dotenv v1.1 thêm `python-dotenv==1.2.4`; environment-lock và ma trận B0/A1 trong gói v1 là bằng chứng lịch sử của nguồn v1, không được đổi hash thành nguồn mới. Khi đo so sánh mới phải chạy các cấu hình cùng nguồn mới.

```powershell
$env:OPENAI_API_KEY = '<khóa của bạn, chỉ nhập trên máy cục bộ>'
$env:OPENAI_MODEL = 'gpt-4.1-mini'
.\.venv\Scripts\python.exe -m llm.smoke --live --output runs/w7-api-smoke-new
```

`--live` gọi tối đa một request có tính phí, output tối đa 64 token; chỉ xác nhận kết nối/hợp đồng. Smoke tự cấp tên mới nếu output đã tồn tại, ví dụ `w7-api-smoke-new-02`, và in thư mục được dùng. Những runner benchmark khác vẫn yêu cầu thư mục output mới.

## Giao diện Trung cần thực hiện

Tạo module riêng, ví dụ `llm/fallback.py`, xuất hàm:

```python
def resolve(packet, client):
    # Trung: chọn top-k, viết instructions và chính sách bỏ cuộc.
    # client.generate_json(instructions=..., payload=..., schema=...)
    # Trả dict có đúng decision, candidate_id, reason.
    ...
```

`client` là transport đã giới hạn theo bước; chỉ dùng `generate_json()`. Có thể import `DECISION_SCHEMA` từ `w7.contracts`. Mỗi trường hợp trả một trong hai dạng:

```json
{"decision":"select","candidate_id":"c2","reason":"Giải thích ngắn"}
```

```json
{"decision":"abstain","candidate_id":null,"reason":"Thiếu bằng chứng"}
```

Packet gồm action, goal nghiệp vụ, descriptor, trigger, ứng viên tương thích và gợi ý top-k semantic. `candidate_id` chỉ có hiệu lực trong snapshot đó. Không dùng mã task để tra đáp án, không đọc các tệp `evaluation-only.json` trong resolver. `context_text` đến từ DOM, cần được coi là dữ liệu không đáng tin cậy khi xây prompt.

## Lệnh chạy sau khi có resolver

Gói có record ở `Evidence/W07/binh/record` để dùng trực tiếp làm `--record` khi nguồn W6 khớp manifest. Máy chuẩn bị còn có `runs/w6-record-v1`; `Evidence/W06/online/record` cũng dùng được nếu hash khớp. Máy khác chưa có record hoặc đổi nguồn phải tạo lại:

```powershell
.\.venv\Scripts\python.exe -m w6.run_heal --mode record --output runs/w7-record-new
.\.venv\Scripts\python.exe -m w7.run_agent --agent b0 --output runs/w7-b0-new
.\.venv\Scripts\python.exe -m w7.run_agent --agent a1 --record runs/w7-record-new --output runs/w7-a1-new
.\.venv\Scripts\python.exe -m w7.run_agent --agent a2 --record runs/w7-record-new --resolver llm.fallback:resolve --max-requests 20 --max-output-tokens 512 --max-reserved-output-tokens 10240 --output runs/w7-a2-new
```

20 request là hạn mức mặc định cho thử nhỏ, không phải bảo đảm đủ benchmark. Khi hết ngân sách, lượt cần model phải lỗi/bỏ cuộc và vẫn được tính trong mẫu số. Chốt ngân sách phù hợp trước lượt đo chính thức; không tự tăng trong khi đo.

```powershell
.\.venv\Scripts\python.exe -m w7.case_audit --output runs/w7-cases-new
.\.venv\Scripts\python.exe -m w7.challenge_eval --dataset runs/w7-cases-new --resolver llm.fallback:resolve --output runs/w7-cases-model-new
.\.venv\Scripts\python.exe -m w7.report runs/w7-b0-new runs/w7-a1-new runs/w7-a2-new --output runs/w7-comparison-new.json
.\.venv\Scripts\python.exe -m w7.plan --goal 'Đổi số điện thoại của hoa@example.com thành 0909998888.' --output runs/w7-openai-plan-new
```

Lệnh `w7.plan` chỉ sinh intent/plan/semantic steps, không thao tác browser. Hai phần planner và fallback dùng cùng model cấu hình qua `OPENAI_MODEL`; kết quả planner W3 dùng Qwen trước đây không đổi nhãn thành kết quả GPT-4.1 mini.

Rate card tùy chọn cho `w7.report --rates rates.json`: `date`, `source` và đơn giá USD/triệu token `input_per_million`, `cached_input_per_million`, `output_per_million`. Lấy giá chính thức tại ngày đo. Chạy A1/A2 cùng phiên bản mã đã khóa; report cố ý từ chối nếu hash nguồn khác.

## Phần Trung làm tiếp, theo thứ tự

1. Kiểm cấu hình khóa/model/quota trên máy chạy. Smoke thật đã đạt trên máy chuẩn bị ở bản dotenv v1.1; máy khác cần kiểm lại với cấu hình của mình.
2. Viết resolver/prompt và top-k, xử lý refusal/incomplete/abstain; giữ validate candidate ở executor.
3. Chạy bộ DOM khó: C01 phân biệt form nghiệp vụ, C02 thiếu bằng chứng cần bỏ cuộc, C03 phân biệt SKU, C04 không có control. Các ca phát triển đã dùng thiết kế; không gọi là held-out.
4. Bổ sung `check_found()` và chính sách nghi sai đích; trigger hiện tại chỉ là B0 count != 1 và semantic abstention. Áp dụng cùng kiểm tra cho A1/A2.
5. Chọn ngưỡng/giảm nhiễu `id/name` trên dev. Nếu sửa nguồn W6 đã đóng băng, phải version và record lại theo chính sách, không sửa evidence cũ.
6. Nối target từ planner adapter vào matcher và binding runtime; hoàn thiện demo yêu cầu tự nhiên đến browser. Không lấy locator cố định của harness W3 làm bằng chứng semantic matching.
7. Khóa prompt/cấu hình rồi chạy lại B0/A1/A2 cùng phiên bản. Chấm nhãn đích độc lập, phân tích lỗi/token/latency/chi phí, review và hoàn thiện báo cáo chung.

## Giới hạn và nguồn tham khảo

- Tại thời điểm đóng gói v1 chưa có API key: các test SDK dùng HTTP giả lập. Bản dotenv v1.1 đã có smoke API thật đạt; chưa đo chất lượng GPT-4.1 mini trên nghiệp vụ.
- Chưa có resolver/prompt cuối của Trung, chưa có benchmark A2 hoặc demo planner end-to-end. Không công bố cải thiện do LLM trước khi có lượt chạy thật.
- Ma trận W6 dễ, A1 có thể không cần LLM. Bộ challenge được tách riêng để kiểm fallback; kết quả fixture không cộng vào task-success MiniBiz.
- Bộ chấm wrong-target online chưa hoàn thiện, giữ số chữa nhầm là null. Không truy cập held-out W11.

Tài liệu chính thức: [model](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [OpenAI Python SDK](https://github.com/openai/openai-python).
