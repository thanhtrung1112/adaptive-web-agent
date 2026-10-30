# W3 hybrid planner — evidence ngày 28/10/2026

- `summary.json`: phạm vi, số ca và giới hạn kết luận.
- `review.json`, `review.csv`: review intent/kế hoạch theo từng goal.
- `real_model_v1/`: lượt phát triển đầu, giữ cả lỗi.
- `real_model_v2/`: sáu ca lượt cuối, trace model thật + intent + workflow + plan.
- `new_wording/`: hai yêu cầu diễn đạt/tham số mới sau khi cố định prompt.
- `m0/`: kiểm chứng năm ca bằng browser thật trên database tạm và API đọc lại.
- `software_tests.log`: toàn bộ 81 test đạt; fixture không phải bằng chứng LLM tự hiểu.
- `metadata.json`: commit nền, trạng thái chưa commit, packages và source hashes LF.
- `manifest.json`: SHA256 các artifact sau chuẩn hóa newline LF.

Kết quả lượt cuối: 8/8 schema/status và review kế hoạch của assistant; 5/5 ca có
thao tác được xác nhận dữ liệu lưu khớp intent. Đây là tập phát triển nhỏ, không
phải 100% success rate trên benchmark hay đánh giá held-out W11. Harness M0 dùng
adapter accessibility cố định, không đo semantic ranking hoặc recovery.

Ghi chú Support chưa có dấu ngoặc kép: model giữ dấu chấm cuối câu trong nội dung
ghi chú. Cần đặt nội dung trong ngoặc kép nếu muốn phân biệt dấu kết câu và dữ liệu.
Review của assistant không thay chữ ký xác nhận của hai thành viên hoặc thầy.
