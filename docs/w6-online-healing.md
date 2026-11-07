# W6 — Runner online và bàn giao phần Bình

## Phạm vi

Runner `w6/run_heal.py` nối B0 với lõi `healing/` của Trung trên MiniBiz. Đây là
replay các script nghiệp vụ đã biết, không phải agent lập kế hoạch web tổng quát.
Không gọi LLM, không sửa selector theo seed, không dùng oracle tìm đích khi heal.

Phân công theo bàn giao: A1 đóng băng mutation set; A2 record descriptor; A3 chạy
healing online; A4 ma trận 390 lượt; A5 demo/logs; A6 chính sách và evidence.
Mã và phân tích được chuẩn bị có hỗ trợ Codex; review của Trung và việc nộp LMS
phải được xác nhận riêng.

## A1 — Mutation set W6-v1

`data/w6-mutation-set-v1.json` đóng băng mode, seed **17/18**, 30 task, seed dữ liệu,
hash LF của mã nguồn, và audit trên **143 trạng thái M0 trước thao tác**. Công thức
mutation 0.5.0 được giữ nguyên; đây là cấu hình dataset phát triển mới, không ghi
đè manifest/bằng chứng W5 17/23 và không dùng held-out W11.

Audit loại hidden mutation/seed và query mutation/seed trong href/action/script
src trước khi so cấu trúc DOM. Theo phép so này, 17/23 trùng ORDER và STRUCTURE ở
143/143 trạng thái, còn 17/18 không trùng ở cả sáu mode. Số này khác báo cáo offline
cũ 119/143 và 72/143 vì báo cáo cũ so toàn bộ HTML bao gồm thông tin transport.
Không xem đổi số seed hay đổi URL đơn thuần là tăng đa dạng DOM; không xem các
task cùng mẫu form là các workflow độc lập.

## A2 — Record

Chế độ `record` chạy B0 nguyên bản ở M0, mặc định CSS. Mỗi task reset DB tạm và tạo
browser context mới. Mỗi bước không phải `goto` phải có đúng một locator B0;
snapshot M0 được thu trước thao tác và `build_descriptor()` tạo descriptor.

`descriptors.json` có **143 descriptor** với task/bước, action và script gốc,
không chứa `element_id`, `xpath`, `target_element_id`, `ref_eid` trong descriptor.
Chỉ sau khi mọi bước hoàn tất và API/CSV đạt, task mới đủ điều kiện dùng làm record.
Runner từ chối record thiếu task/bước, khác manifest hoặc khác script/locator.

## A3 và A6 — Heal

Chính sách được ghi tại `docs/decisions/W6-online-trigger-policy.md`:

1. B0 khớp một phần tử: thực thi B0.
2. B0 khớp 0 hoặc nhiều phần tử: thu DOM hiện tại, rút control với XPath và gọi
   `heal(descriptor, candidates)` theo cấu hình C (`features`, margin 0.02,
   ordinal bật, min_score 0.0).
3. Chỉ thao tác nếu `healed` và XPath mới khớp một phần tử; tối đa một lần heal/bước.
4. Nếu bỏ cuộc hoặc thao tác lỗi thì dừng task, giữ trace của bước lỗi.
5. API/CSV chấm mục tiêu cuối; API không thao tác thay UI và không cung cấp đáp án
   cho ranker. Mục tiêu phải chưa thỏa trên seed trước khi thực thi.

Trace JSON từng lượt giữ B0 count, trigger missing/multiple, quyết định heal,
top-k, điểm, XPath được thực thi, thời gian, lỗi và kết quả API cuối task. Snapshot
có hash HTML để kiểm chứng đường dẫn đích tại thời điểm quyết định.

## A4 — Ma trận và cách đọc kết quả

30 task × (M0 chạy một lần + 6 mode × seed 17/18) = **390 lượt**; record M0 30 lượt
là giai đoạn chuẩn bị riêng. Demo là lượt riêng, không cộng vào ma trận benchmark.

`task_recovery_rate` là số task có gọi healing và cuối cùng đạt tất cả bước/API
chia cho số task có gọi healing. `heal_actions_succeeded` chỉ có nghĩa thao tác
Playwright hoàn tất, không chứng minh độc lập phần tử được chọn đúng. Số chữa
nhầm online chưa có nhãn độc lập được giữ `null`, không tự ghi bằng 0.

Giới hạn: chưa kiểm `wrong_target` khi B0 khớp đúng một phần tử; timeout/hidden/
disabled không kích hoạt healing; CSS không bị ảnh hưởng ở mọi trục. Số trigger
ở trạng thái sau phục hồi không phải một full B0 matrix độc lập. Timing bao gồm
thu DOM/ghi trace và API, không dùng để so trực tiếp với timing W4/W5.

Kết quả thực chạy, metadata và CSV nằm trong `Evidence/W06/online/`; không dùng
các con số offline 1.716 cặp làm recovery online của runner này.

## A5 — Demo

Hai luồng minh họa: T004 (đơn nhiều dòng) và T010 (CRM → Order → Support), chạy
W5_COMBINED trên cả hai seed. Trace/ảnh trong `Evidence/W06/online/demo/`; video
đầy đủ local ở `runs/w6-demo-v1/`. Video có thể đóng gói riêng để nộp LMS, không
đưa timing demo vào benchmark. Các ca `multiple` và `no_candidates` được kiểm
bằng test browser riêng, không thêm vào 390 lượt đã đóng băng.

## Tái lập

Chạy tại thư mục repo, sử dụng môi trường `.venv` đã có NumPy và Playwright:

```powershell
# Dùng M0 pre-action HTML từ bộ W4 đầy đủ để audit seed trước khi đo kết quả.
.\.venv\Scripts\python.exe -m w6.freeze --dataset runs/w4-development-lf
.\.venv\Scripts\python.exe -m w6.run_heal --mode record --output runs/w6-record-v1
.\.venv\Scripts\python.exe -m w6.run_heal --mode heal --record runs/w6-record-v1 --output runs/w6-online-v1
.\.venv\Scripts\python.exe -m w6.run_heal --mode heal --record runs/w6-record-v1 --output runs/w6-demo-v1 --tasks T004 T010 --mutations W5_COMBINED --demo
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m w6.evidence --run runs/w6-online-v1 --record runs/w6-record-v1 --demo runs/w6-demo-v1 --output Evidence/W06/online
.\.venv\Scripts\python.exe -m w6.evidence --verify Evidence/W06/online
```

Manifest đã đóng băng có thể dùng trực tiếp nếu source hash khớp, không cần chạy
lại `freeze` để tái lập runner. Các output phải là thư mục mới; không ghi đè một
lượt đo cũ. Không chạy đồng thời hai task trong cùng process/DB của một lượt đo.
`w6.evidence` kiểm tra đủ ma trận, descriptor, trace, CSV, summary, snapshot HTML
và checksum artifact. Không đóng gói database hoặc server log.
