# W4 — Bàn giao phần Vũ Văn Bình

## Phạm vi và cách đọc kết quả

Đề cương W4 (18–24/10/2026): semantic locator ranking; output embedding baseline;
input 30 tasks × mutations. Phần Bình chuẩn bị app/dữ liệu và kiểm chứng nghiệp vụ.
Phần embedding/semantic ranking và số đo chung còn cần Trung tích hợp, review.

`w4.run` sử dụng **evaluation oracle** biết quy tắc mutation để thực hiện thao tác.
Nó chứng minh task còn giải được trên app thật, không đo khả năng thích nghi.
Không gán tỷ lệ oracle đạt cho B0, B1, A1, A2 hoặc embedding.
`baseline.run_baseline` vẫn dùng nguyên CSS/XPath viết tay, không dịch locator.
`w4.b0_probe` chỉ đo T004 để phân biệt locator vỡ với app hỏng, không phải ma trận B0 đủ 30 task.

## Tệp Trung cần đọc theo thứ tự

1. `data/w4_mutations.json`: mutation/seed phát triển, task hash, phạm vi.
2. `tasks/tasks_w4.json`: T001–T030; 20 object đầu bằng nguyên W2.
3. `dom_snapshot/schema_v0.1.json`, `docs/dom-snapshot-v0.1.md`: schema giữ v0.1.
4. `w4/dataset.py`: hàm `ranking_inputs(root, pair)` để lấy descriptor/candidates.
5. `w4/integration_example.py`: nối ranker W3 với dữ liệu app thật.
6. `results/w4/binh_v1/`: metadata, kết quả replay, mẫu snapshot và ground truth riêng.
7. `docs/decisions/W4-render-mutations.md`: quyết định triển khai và giới hạn.

Không import `w4/oracle.py` hoặc `app.mutations.opaque_id` vào ranking/embedding.
Không truyền `target_element_id`, task goal, success criteria, cookie hoặc pair metadata vào ranker.

## Mutation v1 trên app thật

| Mức | Biến đổi | Bảo toàn |
|---|---|---|
| M0 | Identity HTML | Locator và luồng W2 |
| M1 | ID opaque theo FNV-1a 64-bit + seed; cập nhật for/ARIA IDREF/fragment | name gửi form, class CSS, option value |
| M2 | Nhãn/button/link/placeholder theo từ đồng nghĩa cố định + seed | Giá trị dữ liệu, option value, API |
| M3 | 1 hoặc 2 span `display:contents` quanh control | Semantics form/bảng; không bọc tr/td/option |

M1 chỉ hiện thực biến thể đổi ID, chưa randomize mọi class/name/data-*.
M3 có hai kiểu độ sâu wrapper; không phải M4 layout hay mutation kết hợp M5.
Cookie `minibiz_mutation` giữ mode/seed trong browser context. Redirect có query context;
GET form có hidden context. Link/form giữ href/action cũ và dùng cookie để tránh gây nhiễu
selector href B0 hoặc đặc trưng form trong ranking.
Vào `?mutation=M0&seed=0` để về M0. Mỗi run/task phải dùng context mới.
Query sai mode hoặc seed ngoài 0..2147483647 trả HTTP 400. API/static không mutation.

## Chạy từ thư mục gốc repo — PowerShell

Môi trường `.venv` hiện có, không cần activate nếu dùng Python tường minh:

```powershell
.\.venv\Scripts\python.exe scripts/validate_tasks.py tasks/tasks_w4.json
.\.venv\Scripts\python.exe scripts/seed_manifest.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m w4.run --seeds 7
```

Runner tự tạo server cổng rảnh/SQLite tạm, reset từng task, context mới; không sửa database
đang làm việc hoặc dùng server cổng 8000. Output mới: `runs/w4_<timestamp>/`.
Lần đầu trên máy khác chỉ cài requirements-lock và Playwright Chromium theo README nếu thiếu.

Kiểm tra nhanh 4 task đại diện, hoặc thêm seed phát triển thứ hai:

```powershell
.\.venv\Scripts\python.exe -m w4.run --tasks T021 T024 T029 T030 --seeds 7 8
.\.venv\Scripts\python.exe -m baseline.run_baseline --task-file tasks/tasks_w4.json --mode both
.\.venv\Scripts\python.exe -m w4.b0_probe
```

Các lệnh B0 dưới mutation có thể trả exit code 1 khi locator vỡ; đọc `error`, `failed_step`,
`failed_locator`. Không đánh dấu app lỗi nếu oracle cùng task/variant vẫn qua success criteria.
Muốn chạy B0 đủ matrix: lặp từng M0/M1/M2/M3 bằng `--mutation Mx --mutation-seed 7`;
mọi thất bại vẫn được lưu. Phần đo đầy đủ này cần thống nhất với Trung.

Sau khi lấy đường dẫn output vừa in:

```powershell
.\.venv\Scripts\python.exe -m w4.validate_dataset runs/<run_id>
.\.venv\Scripts\python.exe -m w4.integration_example runs/<run_id>
.\.venv\Scripts\python.exe -m w4.publish runs/<run_id> results/w4/<ten-moi>
```

Thay các placeholder bằng tên thật; output runner/publisher phải là thư mục chưa tồn tại.
`integration_example` chỉ là smoke adapter dùng W3 ranker, không phải embedding baseline.

## Hợp đồng dữ liệu

Full run chứa:

- `metadata.json`: HEAD, dirty status, hash LF mã nguồn, seed/task hash, Python/browser,
  các seed phát triển và protocol thực chạy. HEAD không đồng nghĩa code sạch; phải đối chiếu hash.
- `results.csv`, `summary.json`, `traces.json`: task/variant đã replay và kết quả API/download.
- `snapshots/<id>/{dom.html,features.json}`: ảnh chụp DOM runtime trước mỗi thao tác và sau task.
  Provenance có mutation, mutation_seed, data_seed, git_commit và seed_sha256.
- `ground_truth/pairs.json`: riêng phía evaluator; M0 reference và target ở biến thể,
  ghép theo task + step_index của cùng script. Không giữ stable target ID trong HTML.
- `coverage.json`: các task/step/state thực thu. `validation.json`: schema, HTML SHA-256,
  ID tham chiếu và tính nhất quán của pair.

`element_id` chỉ có nghĩa trong từng snapshot. Phần tử đích có thể có ID khác giữa M0/M3;
không so sánh element_id bằng nhau để chấm. Khởi tạo input:

```python
from w4.dataset import ranking_inputs

# pair được evaluator đọc từ ground_truth/pairs.json, không đưa trực tiếp cho ranker.
descriptor, candidates = ranking_inputs(dataset_root, pair)
ranking = your_embedding_ranker(descriptor, candidates)
# Chỉ evaluator dùng pair['target_element_id'] sau khi ranker trả kết quả.
```

V0.1 của adapter dùng `candidates.features.controls` hiện có, chưa sửa thuật toán Trung.
Những trường không được adapter xuất (ví dụ name_hint) vẫn có trong snapshot nếu Trung cần
bổ sung đặc trưng. Mọi mở rộng phải giữ ground truth ngoài input và có kiểm thử.

## Bản gọn và dữ liệu đầy đủ

`results/w4/binh_v1/summary.json` phản ánh full replay; snapshot công bố trong thư mục này chỉ
là mẫu trạng thái cuối trước hành động của T001/T004/T006/T009/T024/T030, không phải đủ các bước.
`coverage.json`, `manifest.json` và `validation.json` nêu rõ hai phạm vi.
Full snapshots ở `runs/` (Git ignore) và có thể tái sinh bằng lệnh `w4.run`.
Nếu cần chuyển dataset đầy đủ, dùng Drive/Git LFS cùng checksum/manifest; không commit model weights.
Không dùng held-out W11. Chưa có số liệu embedding trong evidence phần Bình.

## Kiểm tra thủ công bằng database riêng

```powershell
New-Item -ItemType Directory -Force runs | Out-Null
$env:MINIBIZ_DB_PATH = Join-Path $PWD 'runs/w4-manual.sqlite3'
.\.venv\Scripts\python.exe scripts/reset_db.py --yes
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8004
```

1. Mở `/orders/new?mutation=M1&seed=7` tại `http://127.0.0.1:8004`.
   DevTools thấy ID opaque, label vẫn gắn đúng input; thêm 3 dòng, xóa 1, chọn 2 SKU khác nhau,
   nhập số lượng rồi tạo đơn. API `/api/orders/<mã đơn>` phải có đủ hai SKU/qty.
2. Mở `/customers?mutation=M2&seed=7`; tìm email `pham.ha@example.com`, mở chi tiết.
   Nhãn đổi nhưng tìm kiếm và liên kết vẫn hoạt động; `/api/session/last_viewed_customer` trả email đó.
3. Mở `/orders/new?mutation=M3&seed=7`; inspect thấy wrapper span, tiếp tục thêm/xóa và tạo đơn.
   Chức năng không đổi; một số XPath label/following-sibling cũ sẽ không còn khớp.
4. Lọc ngày và xuất CSV ở `/orders`; tải đúng danh sách, không có HTML bị chèn vào CSV.
5. Vào `/customers?mutation=M0&seed=0`; ID và nhãn gốc trở lại.

Ctrl+C để dừng server, sau đó `Remove-Item Env:MINIBIZ_DB_PATH` trong terminal này.
Reset ở ví dụ chỉ xóa database thử nghiệm `runs/w4-manual.sqlite3`.

## Tiêu chí bàn giao

- Bộ 30 task hợp lệ, 20 task cũ giữ nguyên; mục tiêu chưa đạt khi chưa thao tác.
- M0 và các mutation chạy đúng nghiệp vụ bằng oracle; có metadata/cấu hình thực chạy.
- Tái lập mutation và giữ context, IDREF, form động, CSV; test hash/schema/pair có ca âm.
- Trung đọc được input xếp hạng và thay ranker mẫu bằng embedding.
- Chưa hoàn tất W4 chung cho tới khi có embedding baseline, đánh giá chung và review chéo.

Các giới hạn còn giữ: trọng số/ranking W3 chưa đổi; không có M4/M5/iframe/shadow DOM/LLM;
timestamp đơn mới có thể khác giữa các replay độc lập (mutation tái lập trên cùng trạng thái render).
Port server/URL tuyệt đối cũng có thể khác giữa các run cô lập; không dùng byte hash toàn bộ hai run
để kết luận mutation không tái lập. Hash trong manifest xác nhận nguyên vẹn từng artifact của chính run đó.
Critical_elements T015–T017/T019 trong W2 có mô tả mã đơn/ticket kế thừa chưa chính xác;
giữ nguyên các object theo yêu cầu, evaluator dựa success criteria và script đúng, ghi errata ở decision log.
