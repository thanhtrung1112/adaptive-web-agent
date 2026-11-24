# Tuần 7 — Đánh giá phục hồi trên website thực

GVHD yêu cầu nhóm 5 đánh giá trên website và tình huống thực, đồng thời đo phục hồi nhầm, độ trễ và chi phí. Bộ kiểm thử dùng bốn tác vụ điều hướng trên tài liệu công khai của [Python](https://docs.python.org/3.13/tutorial/index.html) và [SQLite](https://www.sqlite.org/docs.html).

## Kết quả ngày 23/11/2026

Đã chạy 72 lượt bằng Chrome, gồm 36 lượt cho mỗi cấu hình. Các lượt A2 dùng API thật và nhận model `gpt-4.1-mini-2025-04-14`. B0 mở đúng 4/4 liên kết gốc và thất bại ở 8/8 ca có thay đổi DOM trong mỗi cấu hình.

| Cấu hình | Agent | Phục hồi nhầm | Mở đúng link đã đổi nhãn | Dừng đúng khi link bị xóa | Phục hồi trung vị / p95 | Gọi API | Chi phí API ước tính |
|---|---|---:|---:|---:|---:|---:|---:|
| Theo ngữ cảnh | A1 | 4/8 | 0/4 | 2/4 | 0,194 / 0,256 giây | 0 | 0 USD |
| Theo ngữ cảnh | A2 | 5/8 | 2/4 | 1/4 | 0,850 / 1,981 giây | 4 | 0,0034172 USD |
| Theo URL đích | A1 | 0/8 | 0/4 | 4/4 | 0,193 / 0,494 giây | 0 | 0 USD |
| Theo URL đích | A2 | 0/8 | 3/4 | 4/4 | 1,714 / 2,246 giây | 8 | 0,0048796 USD |

Guard theo URL đích chặn 4 đề xuất sai của A1 và 6 đề xuất sai của A2. A2 tăng số ca mở đúng sau khi đổi nhãn từ 2 lên 3, với độ trễ và chi phí cao hơn. Ca đổi nhãn `SQL-CLI` còn bỏ cuộc. Heuristic đề xuất sang mục TCL và guard đã chặn. Sau đó LLM thấy nhãn mới nhưng trả `abstain` vì đánh giá nhãn và dạng `href` khác mô tả đã ghi. [Trace theo URL đích](destination/results.json)

- Guard theo ngữ cảnh. [Số liệu tổng hợp](context/summary.json) · [Trace 36 lượt](context/results.json) · [Nhật ký API](context/llm-calls.jsonl)
- Guard theo URL đích. [Số liệu tổng hợp](destination/summary.json) · [Trace 36 lượt](destination/results.json) · [Nhật ký API](destination/llm-calls.jsonl)

Nhật ký API công bố lược bỏ mã request và response của nhà cung cấp. Bản gốc ở thư mục `runs/` trên máy chạy.

## Cách chạy lại

Chạy tại thư mục gốc repo với Chrome đã cài và cấu hình OpenAI cục bộ. Mỗi lệnh có `--live` dùng tối đa tám yêu cầu GPT-4.1 mini. Bỏ `--live` nếu chỉ cần đo B0 và A1.

```powershell
.\.venv\Scripts\python.exe -m w7.real_site_eval --channel chrome --live --link-guard context --output runs/w7-context-repeat
.\.venv\Scripts\python.exe -m w7.real_site_eval --channel chrome --live --link-guard destination --output runs/w7-destination-repeat
```

## Thiết kế đo

- Tác vụ gồm mở chương Data Structures, chương Input and Output, trang SQL Syntax và trang Command-Line Interface. Mỗi tác vụ chạy trong ba tình huống. Trang gốc là ca đối chứng. Ca đổi nhãn đổi cả cách biểu diễn `href` từ tương đối thành tuyệt đối nhưng giữ nguyên đích. Ca xóa liên kết kiểm tra việc dừng khi mục tiêu vắng mặt. Thay đổi DOM chỉ áp dụng trong phiên trình duyệt thử nghiệm.
- B0 dùng locator CSS đã ghi. A1 dùng heuristic và kiểm tra ứng viên. A2 gọi LLM khi heuristic bỏ cuộc hoặc ứng viên bị kiểm tra loại. Cấu hình `context` dùng guard từ vựng tuần 7. Cấu hình `destination` kiểm tra URL cùng origin dựa trên `href` đã ghi, dùng cho tác vụ điều hướng chỉ đọc có đích ổn định.
- Bộ chấm dùng node gốc được nhận diện từ vai trò, nhãn hiển thị và URL đã đăng ký. Node chấm điểm được giữ ngoài bộ xếp hạng và prompt. Khi agent chọn đúng node, trình duyệt thực hiện điều hướng và xác nhận URL, phản hồi HTTP và tiêu đề trang. Khi agent chấp nhận node sai, bộ chấm ghi `wrong_recovery` và dừng trước khi bấm.
- Tỷ lệ phục hồi nhầm là số lần chấp nhận sai đích chia cho số lượt kích hoạt phục hồi. Ứng viên sai bị guard chặn được ghi riêng. `correct_abstention` nghĩa là agent dừng khi node đích đã bị xóa. B0 có mẫu số phục hồi bằng 0.
- Thời gian tác vụ tính cả tải trang, bước chuẩn bị và điều hướng. Thời gian phục hồi tính từ khi locator hỏng đến khi có quyết định hoặc lỗi, gồm chụp DOM, xếp hạng, kiểm tra và gọi LLM nếu có. Chi phí USD ước tính dùng token thực và [đơn giá GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) ngày 23/11/2026.

Bộ ca này giới hạn ở điều hướng công khai có độ thay đổi DOM được kiểm soát. Các tác vụ biểu mẫu, URL đích thay đổi và website cần đăng nhập nằm ngoài phạm vi phép đo này.
