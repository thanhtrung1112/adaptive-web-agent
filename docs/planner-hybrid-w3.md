# W3 bổ sung: planner kết hợp LLM và quy trình MiniBiz

Ngày 28/10/2026. Phạm vi: hiểu yêu cầu và lập kế hoạch browser theo lịch đánh giá mới.
Qwen3.5:4b chạy local qua Ollama, `think=false`. Đây là thiết kế kết hợp: LLM trích ý
định/tham số; Python dựng bước từ quy trình đã biết. Không tuyên bố LLM tự suy ra toàn
bộ thao tác. Các lượt planner trực tiếp trước đây được giữ để đối chiếu lỗi phát triển.

## Kiến trúc

`goal -> LLM -> intent có source span -> kiểm tra dữ liệu -> quy trình -> plan + workflow`

- `planner/intent.py`: hợp đồng intent 1.0, prompt và kiểm tra source có thật trong goal.
  Mỗi operation có `kind`, `slots` (key/value/source), `items` (sku/quantity/source).
- `planner/workflows.py`: sáu nghiệp vụ: tìm khách, tạo khách, đổi số điện thoại, tạo
  đơn nhiều dòng, tạo ticket, đóng ticket. Dựng kế hoạch độc lập mã task.
- `planner/hybrid.py`: gọi LLM local, tối đa một lần sửa lỗi hợp đồng; lưu phản hồi,
  intent, plan, workflow, tokens được báo cáo, thời gian, model digest và source hashes.
  LLM lỗi thì ghi lỗi; không dùng fixture thay thế để báo thành công.
- `planner/schema.json`: giữ plan schema 0.2; không đổi hợp đồng DOM hoặc ranker của Trung.
- `planner/verify_m0.py`: harness kiểm tra tính khả thi trên M0 bằng adapter label/role
  cố định và API đọc trạng thái. Chỉ chạy server/database tạm; không dùng để chấm ranking.

Một yêu cầu nhiều nghiệp vụ được chia operation. Thiếu bất kỳ trường bắt buộc nào thì
plan trả `needs_clarification`, gom tất cả câu hỏi và không sinh bước cho cả yêu cầu.
Yêu cầu chứa nghiệp vụ ngoài phạm vi trả unsupported, không thực thi một phần.

## Hợp đồng và ràng buộc

Plan vẫn có objective, entities, questions, steps, verification. Workflow 1.0 đi kèm
ghi control ngữ nghĩa, operation_index, row và chỗ sinh runtime binding.
`validate_workflow(plan, workflow, request, intent)` kiểm tra:

- Mở form sửa trước khi nhập số; nhập đủ trường trước khi lưu.
- Chọn khách hàng/SKU bằng select; trường nhập bằng fill.
- Dòng đầu đã có sẵn; chỉ thêm dòng từ sản phẩm thứ hai, không để dòng trống khi lưu.
- Giá trị trong kế hoạch và workflow khớp intent đã kiểm tra source.
- Thứ tự operation và nguồn tham chiếu hợp lệ; không dùng đối tượng chưa được tạo.
- Giới hạn max_steps, đường dẫn entry được phép, không đưa CSS/XPath vào plan.

`$last_customer` được gắn với email đã lưu thành công. `$last_order` phải lấy mã đơn
thật trên trang kết quả, không cộng ID từ seed. Harness giữ tham chiếu theo từng
operation để không nhầm khi tạo nhiều đối tượng. Khi tích hợp matcher, Trung cần
đọc các target ngữ nghĩa, thu DOM hiện tại và cung cấp adapter riêng; control metadata
không được đưa thành đặc trưng để đánh giá ranking hoặc làm ground truth rò rỉ.

Source span chỉ chứng minh giá trị xuất hiện trong goal; không chứng minh LLM đã
gán đúng nghiệp vụ. Cặp SKU/số lượng yêu cầu source hẹp, chứa đúng SKU và đúng một số
lượng ngoài SKU. Chưa xử lý số lượng viết bằng chữ, gộp SKU lặp hoặc mọi cách diễn đạt.
Tên/ghi chú/tiêu đề nên đặt trong dấu ngoặc kép khi cần phân biệt dấu câu với nội dung.

## Chạy từ thư mục gốc repo bằng PowerShell

```powershell
ollama list
.\.venv\Scripts\python.exe -m planner.hybrid --model qwen3.5:4b --think false --goal 'Đổi số điện thoại của khách hàng.'
.\.venv\Scripts\python.exe -m planner.hybrid --model qwen3.5:4b --think false --goal 'Đổi số điện thoại của tran.hoa@example.com thành 0909998888.'
.\.venv\Scripts\python.exe -m planner.evaluate --mode hybrid --model qwen3.5:4b --think false --output runs/hybrid-review-new
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Output phải là thư mục mới; không ghi đè bằng chứng. `planner.run` vẫn là planner trực
tiếp cũ. `planner.hybrid` dùng kiến trúc kết hợp mới. Evaluator mặc định mode=direct;
phải ghi rõ `--mode hybrid`. Không thay model mặc định hoặc tự tải weights.
Nếu CLI trả needs_clarification, chạy lại với goal đầy đủ sau khi trả lời; chưa có
session hội thoại tự lưu. Timeout 240 giây mỗi request; temperature=0, seed=7,
context=8192 không đảm bảo kết quả giống tuyệt đối giữa phiên bản/phần cứng.

## Kiểm tra thủ công

1. Chạy goal thiếu dữ liệu ở trên: cần hai câu hỏi (email và số mới), steps rỗng.
2. Chạy goal đủ dữ liệu: kiểm tra intent giữ đúng email/phone và source span.
3. Plan CRM cần đi qua tìm email, Tìm, mở chi tiết, Sửa, nhập số, Lưu và verification.
4. Với đơn hai sản phẩm, xem đúng hai dòng, một lần Thêm dòng và đúng từng số lượng.
5. Với chuỗi tạo khách/đơn/ticket, xem `$last_order`; không có mã đơn được đoán trước.
6. Chỉ với trace `ready`, kiểm tra browser trên dữ liệu tạm:

```powershell
.\.venv\Scripts\python.exe -m planner.verify_m0 --trace runs/hybrid-review-new/crm-paraphrase/trace.json --output runs/hybrid-crm-m0-new
```

7. `verification.json` cần có `persisted_state_matches_intent: true`. Vẫn phải review
   intent theo goal: lưu đúng dữ liệu mô hình hiểu sai không phải hoàn thành yêu cầu.
8. Các ca thiếu dữ liệu/unsupported không chạy harness ghi dữ liệu.

Harness dùng locator label/role cố định trên M0, không có recovery/retry. Nó chứng minh
kế hoạch cụ thể có thể thao tác trên MiniBiz, không chứng minh semantic matching của
Trung, robustness M1–M3 hoặc agent tổng quát đã hoàn tất. Không nối trực tiếp harness
này vào thí nghiệm B0/B1/A1/A2 để thay đổi nền so sánh.

## Kiểm chứng và giới hạn nghiệm thu

Ngày 28/10: toàn bộ 81 tests đạt trong 37.455 giây, gồm fixture workflow và browser M0.
Log: `runs/planner-hybrid-tests-20261028.log` (bản evidence sẽ lưu cùng kết quả mới).
Đây là kiểm thử phần mềm, không phải tỷ lệ đúng của LLM. Kết quả real-model được ghi
riêng từng lượt và review theo goal; chưa tự nhận nhóm đã được thầy nghiệm thu W3.

Phạm vi nghiệp vụ hữu hạn; chưa có đổi trạng thái đơn, CSV, gán nhân viên, planning
website ngoài MiniBiz, self-healing hay LLM recovery. Chưa replay đầy đủ 30 task,
không dùng held-out W11. Dữ liệu này là tập phát triển đã dùng sửa prompt, không gọi
là tập test độc lập. Hai thành viên cần review hợp đồng/giới hạn và quyết định nghiệm thu.

### Kết quả thực chạy cuối cùng

`results/w3/hybrid_planner_v1/`: 6 ca phát triển + 2 yêu cầu diễn đạt/tham số mới,
8/8 đúng schema và status, 8/8 đạt review kế hoạch của assistant trong lượt cuối.
Năm ca ready được chạy browser M0 và API đọc lại: 5/5 khớp intent (CRM, đơn hai dòng,
đóng ticket, chuỗi khách/đơn/ticket và đơn có tham số mới). Hai ca thiếu dữ liệu và
một ca unsupported không thực thi. Giữ lỗi lượt đầu ở `real_model_v1/`.

`review.json` ghi từng ca và lưu ý dấu chấm trong ghi chú chưa đặt trong ngoặc kép.
`metadata.json` có hashes nguồn chuẩn LF, packages và commit nền với thay đổi chưa
commit. `manifest.json` kiểm tra byte của artifact; trace model có hashes nguồn lúc
chạy. Các trace lượt cuối đều khớp mã nguồn tại thời điểm đóng gói. Không dùng 8 ca
này để suy ra 100% chính xác trên mọi yêu cầu hoặc thay thế review của nhóm/thầy.

## Bàn giao và GitHub

Trung đọc: intent.py, workflows.py (CONTROLS/TARGETS/validate_workflow), schema.json,
hybrid.py và ví dụ trace mới. Tiếp tục tích hợp matching trên DOM hiện tại theo từng
target; không sửa embedding để khớp đáp án ca thử.

Issue title: `[W3 bổ sung] Hiểu yêu cầu và lập kế hoạch MiniBiz bằng LLM + quy trình`.

Issue body dự kiến: Trích nghiệp vụ/tham số từ goal bằng Qwen local; dựng kế hoạch có
trạng thái và runtime reference; hỏi đủ dữ liệu thiếu; kiểm tra ràng buộc; lưu bằng
chứng model thật và xác minh M0 riêng. Giới hạn sáu nghiệp vụ, không phải locator
recovery. Nghiệm thu theo review intent/kế hoạch và kết quả kiểm chứng được báo cáo.

PR title: `[W3 bổ sung] Hybrid planner, kiểm tra quy trình và bằng chứng M0`.

PR body cần nêu kiến trúc kết hợp, model/cấu hình thực chạy, kết quả review cuối cùng,
81 tests, các ca fail/giới hạn, link evidence và Issue bổ sung thật. Chưa có số Issue;
không dùng #13 (mutation W4). Chưa commit/push/merge. Không add các DOCX, thay đổi W2
hoặc thư mục Evidence/.github đang có của người dùng vào commit planner.
