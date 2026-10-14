# W3 DOM snapshot và parser

Phụ trách: Vũ Văn Bình. Schema **0.1 là đề xuất**, chờ Nguyễn Thành Trung xác nhận khi nối candidate generator. Không triển khai ranking, LLM hoặc self-healing trong phần này.

## Chạy

Từ thư mục gốc repo, dùng môi trường W2 đã cài requirements-lock.txt và Chromium của Playwright:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_dom_snapshot.py -v
.\.venv\Scripts\python.exe -m dom_snapshot.run
```

Runner tự chạy server ở cổng riêng và SQLite tạm đã reset seed, không dùng server cổng 8000 hay sửa database đang làm việc. Kết quả mới nằm trong `runs/dom_W3_<timestamp>/`. `--output <thư-mục-mới>` cho phép chỉ định nơi lưu; runner từ chối ghi đè thư mục đã có. Không tạo demo/video.

## Cấu trúc mã

- `dom_snapshot/extract.js`: đọc DOM hiện tại và trạng thái runtime trong một lần evaluate, không sửa trang.
- `dom_snapshot/capture.py`: metadata, hash HTML, ghi `dom.html` và `features.json`.
- `dom_snapshot/parser.py`: chuẩn hóa gói dữ liệu và kiểm tra schema, ID, quan hệ cha–con. Đây là parser của snapshot runtime; không phải parser HTML ngoại tuyến dùng BeautifulSoup.
- `dom_snapshot/schema_v0.1.json`: hợp đồng dữ liệu máy kiểm tra được.
- `dom_snapshot/cases.py`: định nghĩa trạng thái, ánh xạ task và kiểm tra giá trị mong đợi.
- `dom_snapshot/run.py`: thu mẫu MiniBiz bằng server/database cô lập.
- `tests/test_dom_snapshot.py`: kiểm thử trình duyệt thật và dữ liệu không hợp lệ.

## Hợp đồng bàn giao cho Trung

Mỗi `features.json` chứa schema_version, snapshot_id, task_id, state, URL, title, captured_at_utc, viewport, html_sha256, provenance và elements. Các trường không có giá trị dùng null, không dùng chuỗi "null". visible/enabled/readonly là boolean.

Mỗi phần tử có element_id, parent_id, tag, text, attributes, label, name_hint, visible, enabled, readonly, value, checked, selected, bounding_box và locator. Giữ cả phần tử không tương tác hoặc không hiển thị để Trung tự lọc; thứ tự là DOM preorder. Không đưa đáp án task hoặc success criteria vào đặc trưng.

- `label`: text của label liên kết bằng `for` hoặc label bao ngoài.
- `name_hint`: gợi ý tên theo aria-labelledby, aria-label, label, alt, title. **Không phải triển khai đầy đủ thuật toán accessible name**; Trung có thể dùng text khi name_hint trống.
- `text`: textContent chuẩn hóa khoảng trắng, gồm nội dung con; các node cha có thể lặp text với con. Generator cần lọc tag và phạm vi, không coi mỗi node là một ứng viên tốt.
- `visible`: có bounding box khác 0 và visibility không hidden/collapse. Đây không phải khả năng click: phần tử có thể ngoài viewport, bị che hoặc opacity 0.
- `enabled`: xét native disabled (kể cả fieldset), aria-disabled trên chính node, và tổ tiên inert. Không suy diễn mọi quy tắc ARIA kế thừa.
- `readonly`: phải xét riêng khi chọn ứng viên nhập liệu.
- `locator`: XPath cấu trúc duy nhất trong DOM đang thu. Dùng `page.locator('xpath=' + element['locator']['value'])`. Không cam kết bền khi thêm/xóa node, điều hướng hoặc mutation.
- `element_id`: chỉ có ý nghĩa trong cặp snapshot_id + element_id; không phải ID ổn định giữa các snapshot.

HTML outerHTML không giữ đủ giá trị runtime như input.value; vì thế cần cả JSON. SHA-256 tính trên byte UTF-8 của dom.html. Không dùng metadata/URL port để so sánh byte giữa hai lần chạy; port, timestamp có thể khác.

## Bộ mẫu và giới hạn

Bộ bàn giao mới: `results/w3/dom_samples_expanded_v0.1/`, gồm 17 trạng thái. Bộ 5 trạng thái cũ đã xóa để tránh nhầm; notebook dùng bộ 17 trạng thái này.

| Module | Trạng thái |
|---|---|
| CRM | Danh sách, kết quả tìm email, tạo mới, chi tiết, sửa khách hàng |
| Order | Danh sách, lọc ngày, tạo một dòng, thêm dòng thứ hai, chi tiết, sau cập nhật trạng thái |
| Support | Danh sách, tạo mới, tạo có đơn chọn sẵn, chi tiết, sau gán nhân viên, sau đóng ticket |

`coverage.json` ánh xạ T001–T020 tới các giao diện đại diện dùng chung. Đây không phải bằng chứng replay đầy đủ mọi task: khách hàng/đơn cụ thể, giá trị đầu vào và trạng thái trung gian có thể khác task gốc. Trường task_id trong snapshot là task đại diện; danh sách liên quan nằm ở summary/coverage.

Mỗi trạng thái reset seed trên database tạm để không phụ thuộc thứ tự; các thao tác cập nhật chỉ tác động database này. Kiểm tra kỳ vọng tại `dom_snapshot/cases.py` bao gồm label, value sau select/fill và việc biến mất các control khi đóng ticket. Chỉ DOM M0 main document; chưa iframe/shadow DOM. Dữ liệu tổng hợp MiniBiz, không thu tài khoản riêng tư.


## Nghiệm thu và bước tích hợp

1. Schema hợp lệ, ID không trùng, cha tồn tại trước con; XPath của từng node ánh xạ duy nhất ở thời điểm thu.
2. Nhãn, trạng thái ẩn/disabled/readonly và giá trị runtime đúng trên fixture kiểm thử.
3. Snapshot sau thêm dòng chứa input/select mới và label đúng.
4. Trung đọc mẫu customers-new/features.json, xác nhận trường cần bổ sung, rồi chốt schema. Thay đổi phá vỡ hợp đồng phải tăng phiên bản.
5. Sau khi generator có mã, đo số ứng viên và tỷ lệ phần tử đích xuất hiện trong danh sách. Chưa có số đo candidate recall trong phần Bình thực hiện.

Hai người cùng hoàn thiện notebook DOM feature, chạy tích hợp và review chéo. Ghi Issue W3 và link PR khi tạo; không tự nhận đã hoàn thành toàn bộ W3 chỉ từ bộ mẫu này.
