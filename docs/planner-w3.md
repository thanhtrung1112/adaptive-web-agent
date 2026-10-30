# W3 bổ sung — Hiểu yêu cầu và lập kế hoạch browser

> Bản hiện hành ngày 28/10: xem [planner kết hợp](planner-hybrid-w3.md).
> Các lượt phía dưới là lịch sử phát triển planner trực tiếp; giới hạn và lỗi cũ
> được giữ để đối chiếu, không phải kết luận của phiên bản kết hợp mới.

Phạm vi theo lịch đánh giá thầy được nhóm cung cấp ngày 24/10/2026: nhận goal,
trích đối tượng/tham số và sinh kế hoạch browser có cấu trúc. Đây là planner prototype;
chưa phải agent thực thi end-to-end, semantic matching hay LLM recovery.

## Thiết kế và hợp đồng

`planner/core.py`: prompt và catalog khả năng MiniBiz, lọc input chỉ gồm goal,
start_url, max_steps. Không đọc baseline scripts, success_criteria hay ground truth.
`planner/schema.json`: objective, entities, status, questions, steps, verification.
Schema 0.2: status ready cần verification (target/expected) khác rỗng;
needs_clarification/unsupported không có hành động hoặc verification.
Mỗi bước có action, target ngữ nghĩa, value, url, expected. Không dùng CSS/XPath làm đích.
Navigate chỉ tới entry route được cho phép; detail và ID mới phải được tìm qua giao diện.
Các plan được mô hình sinh theo goal, không tra bảng task ID.

`planner/run.py` gọi Ollama local, lưu trace thành công/thất bại, phản hồi thực,
usage token, latency, model, commit và source hashes. Không ghi suy luận ẩn.
Schema validation không xác nhận mục tiêu đúng hoặc dữ liệu do LLM không bịa.
Không có executor trong phiên bản này; không dùng plan để gọi API ghi dữ liệu.
Verification là yêu cầu xác minh dự kiến, không phải kết quả thành công.

## Chạy PowerShell tại thư mục gốc repo

```powershell
ollama list
.\.venv\Scripts\python.exe -m planner.run --model qwen2.5:latest --goal "Tìm khách hàng có email tran.hoa@example.com và đổi số điện thoại thành 0909998888."
.\.venv\Scripts\python.exe -m planner.evaluate --model qwen2.5:latest --output runs/planner-review-new
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Máy hiện có qwen2.5:latest; không cần tải thêm cho thử nghiệm này. Máy khác phải chọn
model thực có trong `ollama list`. Endpoint mặc định localhost:11434; không cần API key.
Output phải là thư mục mới. Timeout mỗi yêu cầu 240 giây. Tối đa 1 lần sửa lỗi JSON/hợp đồng bằng chính mô hình;
không retry lỗi mạng, không tự đổi mô hình. Trace lưu mọi attempt và tổng usage token.
Context 8192 token, temperature 0, seed 7 chỉ là cấu hình tái lập; không cam kết output giống tuyệt đối giữa
phiên bản Ollama, model hoặc phần cứng. API: https://docs.ollama.com/api/chat.

## Kiểm tra thủ công và bàn giao

1. Chạy goal CRM: objective/entities phải giữ email và số điện thoại chính xác.
2. Kế hoạch cần tìm khách, mở chi tiết, mở sửa, điền số, lưu và xác minh.
3. Chạy goal thiếu thông tin: "Đổi số điện thoại của khách hàng." — cần hỏi email/số mới,
   không thực hiện thao tác. Chạy "Xóa toàn bộ khách hàng." — unsupported.
4. Dùng `planner/cases.json`: sáu ca CRM paraphrase, Order, Support, chain, thiếu và ngoài
   phạm vi. Rubric chỉ ở evaluator; không đưa đáp án mong đợi vào prompt.
5. Mở trace.json kiểm tra từng bước và chấm semantic review riêng. Schema/status đúng
   không thay thế review hoặc API/DB checker. Không báo task success từ planner.

Trung đọc schema.json và core.py. Lớp executor tương lai nhận target/value theo từng bước,
thu DOM hiện tại rồi gọi semantic matching. Không nối trực tiếp plan với descriptor M0:
ranker W3 nhận descriptor phần tử còn planner trả ý định ngữ nghĩa, cần adapter được
review và kiểm chứng trên trang thật. Xử lý tham chiếu "đơn vừa tạo" ở runtime, không đoán ID.

## Issue và PR dự kiến

Title: [W3 bổ sung] Agent hiểu yêu cầu và sinh kế hoạch browser
Body: Bổ sung planner LLM local, schema/validator, xử lý thiếu thông tin/ngoài phạm vi,
CLI và trace. Nghiệm thu bằng ca phát triển, đánh giá nghiệp vụ kế hoạch và ghi giới hạn
chưa executor. Tham chiếu lịch đánh giá mới; không tự gán số Issue hoặc đóng Issue #13.
PR: [W3 bổ sung] LLM browser planner và bằng chứng kiểm thử.
Commit sau khi có Issue thật; dùng mã Issue mới, không commit/push tự động.


## Rubric review kế hoạch (không phải task success)

Mỗi ca ready chỉ được review đạt khi: giữ đúng tham số, không bịa dữ liệu, thao tác phù hợp
control (fill/select), đủ thứ tự và ràng buộc phụ thuộc, có xác minh kết quả cuối.
Plan thiếu bước hoặc sai loại control ghi fail, dù schema hợp lệ. Với dữ liệu thiếu,
phải hỏi đúng trường còn thiếu và không sinh hành động. Ngoài phạm vi phải unsupported.
Ghi riêng kết quả review và kết quả máy kiểm tra schema/status. Các ca đã dùng để sửa
prompt là development set, không gọi là test độc lập hay held-out.

Ví dụ `expected` trong bước fill chỉ là điều kiện mong đợi sau bước đó. Việc field đã đổi
trên form chưa đồng nghĩa đã lưu DB. Bước click lưu và verification vẫn cần executor kiểm tra.
Kế hoạch chain có tham chiếu “khách/đơn vừa tạo” là ràng buộc runtime, chưa có variable
binding/executor ở phiên bản này nên không tuyên bố đã thực thi chain thành công.


## Thay hợp đồng trong quá trình phát triển

Schema planner 0.1 dùng step verify cuối; 0.2 tách verification bắt buộc ra khỏi steps để
điều kiện xác minh xuất hiện rõ trong structured output. Không thay schema DOM W3 0.1.
Các trace thử nghiệm 0.1 được giữ để phân tích lỗi, không đưa thẳng vào consumer 0.2.
Nếu chuyển plan cũ: chuyển step verify thành verification, loại step đó khỏi steps,
đổi version rồi validate lại; không tự chuyển trong runner để che lỗi mô hình.
Guard phát hiện định danh bịa chỉ bao phủ email, SKU/ORD/TCK và chuỗi số >=6 chữ số;
không chứng minh mọi dữ liệu hay thứ tự nghiệp vụ đều đúng. Vì vậy vẫn cần semantic review.


## Trạng thái kiểm chứng ngày 26/10/2026

Planner còn là prototype, chưa đủ bằng chứng nghiệm thu W3. Kiểm thử riêng planner: 10/10 đạt (1.155 giây). Toàn repo: 68 test, một lỗi teardown W4 do Windows khóa server.log (39.311 giây); không ghi toàn bộ đạt.

Review thực tế phát hiện CRM thiếu thao tác tìm/mở chi tiết, Order đảo số lượng và sai loại control, ca thiếu dữ liệu bị guard chặn, chain timeout. Support và từ chối thao tác không hỗ trợ có kế hoạch phù hợp trong lượt phát triển trước, chưa thực thi browser. Lượt sửa prompt ngày 26/10 chỉ có trace CRM hoàn tất; không suy diễn kết quả ca còn lại. Xem `results/w3/planner_development/semantic_review.json`, `software_tests_20261026.json` và `manifest.json`.

Cần cải thiện mô hình/prompt, chạy lại cùng bộ ca và review ngữ nghĩa trước nghiệm thu. Chưa tích hợp hoặc chạy OpenAI API; đổi nhà cung cấp cần adapter và đo lại, không thay validator bằng niềm tin vào mô hình. Chưa commit/push phần bổ sung này.


## Qwen 3.5 4B local

Đã xác nhận máy có `qwen3.5:4b` (Ollama ID d8b0f5e9760c, khoảng 3,3 GB), chạy CPU tại thời điểm kiểm tra. Model mặc định bật thinking. Có thể thử riêng `--think false`; đây là thay cấu hình cần ghi lại khi so sánh chất lượng/latency, không đảm bảo tăng độ chính xác. Không cần API trả phí.

```powershell
.\.venv\Scripts\python.exe -m planner.run --model qwen3.5:4b --think false --goal "Đổi số điện thoại của khách hàng."
```

Kết quả mong đợi: needs_clarification, hỏi định danh khách hàng và số điện thoại mới, steps rỗng; không tự bịa dữ liệu. Trace ghi `think: false`; `null` nghĩa là dùng mặc định model. Kiểm thử tùy chọn thinking và hợp đồng planner ngày 26/10: 11/11 đạt, 2.541 giây. Chưa suy ra tỷ lệ đúng nghiệp vụ từ các test này.

Thử thực tế mặc định Qwen3.5:4b trên CPU: CRM timeout sau 240.270 giây; đã ngắt lượt còn lại để tránh tiếp tục chờ. Bằng chứng cục bộ `runs/planner-qwen35-4b-smoke/`; chưa có điểm chất lượng, chưa chạy đo với --think false.


## Đánh giá Qwen3.5:4b, thinking tắt — 26/10/2026

Đã bổ sung prompt hỏi toàn bộ dữ liệu còn thiếu trong một lượt, chỉ hỏi trường chưa có. Chạy đủ sáu ca phát triển với temperature=0, seed=7, context=8192, think=false. 6/6 đúng schema, 4/6 đúng status mong đợi, 2/6 đạt review kế hoạch (missing và unsupported). Đây là kết quả một lượt trên tập đã dùng sửa prompt, không phải success rate tác vụ browser hay held-out.

CRM bỏ bước Sửa; Order hỏi lại email đã có; Support từ chối thao tác được hỗ trợ; chain thêm thừa dòng trống và đổi tiêu đề ticket. Chưa chọn model làm planner chính. Cần cải thiện biểu diễn trạng thái/form và kiểm tra phụ thuộc bước, rồi đánh giá lại trên cả yêu cầu diễn đạt mới. Chưa nối kế hoạch trực tiếp vào browser.

Bằng chứng: `results/w3/planner_development/qwen35_4b_nonThinking_v2/semantic_review.json`, trace từng ca, summary, model_inventory và manifest checksum ở thư mục cha. Kiểm thử riêng planner 11/11 đạt, 1.654 giây; không thay thế review LLM. Chưa commit/push.
