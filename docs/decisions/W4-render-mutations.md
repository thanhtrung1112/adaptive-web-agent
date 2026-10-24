# W4 implementation decisions — 22/10/2026

Triển khai theo ADR-0001/0002 Accepted; không thay nội dung hoặc scope các ADR đó.

1. Dùng hàm thuần `mutate_html(html, mutation, seed)` trên HTML đã render bởi Jinja,
   áp ở ASGI render boundary chung cho các route. Vẫn là một app, mutation phía server,
   không chỉnh JSON snapshot để giả lập app. Chỉ hỗ trợ HTML do MiniBiz sở hữu, không parser web tổng quát.
2. M1 v1 chỉ đổi ID và tham chiếu tới ID, giữ name/class do vai trò vận chuyển form/style.
   M2 dùng từ đồng nghĩa phát triển, giữ option value; M3 dùng span display:contents hợp lệ trong p.
   Đây là biến thể cụ thể của M1–M3; không tuyên bố phủ mọi phép mutation được mô tả trong benchmark.
3. Cookie theo browser context giữ mode/seed qua link. Giữ href link ban đầu để không khiến
   B0 exact href hỏng do query ngoài loại mutation đang đo. Form action cũng giữ nguyên để
   đặc trưng form không bị nhiễu; GET thêm hidden context, POST dùng cookie, redirect ghi query rõ ràng.
4. orders.js dùng cấu trúc/name nghiệp vụ thay ID/text; FNV-1a giống Python giữ ID/label dòng động.
   Không thêm map original ID hoặc marker đáp án vào DOM.
5. Dùng oracle evaluator riêng để chứng minh nghiệp vụ và tạo ground truth. Ranking chỉ nhận
   source descriptor + candidate features, không dùng oracle hoặc target ID sau mutation.
6. Giữ schema snapshot 0.1, dùng provenance extensible cho metadata W4. Pair file là hợp đồng
   evaluator mới, không thay snapshot/thuật toán Trung. Full replay dữ liệu nằm runs/, mẫu nhỏ đưa results/.
7. T001–T020 giữ nguyên theo yêu cầu. Errata mô tả critical_elements W2: T015–T017 còn ghi ORD-1003,
   T019 còn ghi TCK-2001. Script/success criteria đúng mã của goal. Chưa sửa các object này để
   giữ nguyên tập đối chứng; khi nhóm muốn sửa metadata task cần ghi version/đối chiếu riêng.
8. 10 task mới gồm biến thể và chuỗi trong workflow hiện có (không phải 10 loại workflow mới).
   Không đổi seed_v1 hay làm success criteria đạt sẵn; task T026 kiểm tra CSV tập rỗng.

Không sinh/đọc held-out W11. Không đặt model/token quota/embedding choice thay phần Trung.

Lưu `features.json` bằng LF tường minh ở helper W3; Windows text newline mặc định là CRLF,
trong khi Git checkout dùng LF. Đây là sửa persistence để hash dataset không đổi sau commit,
không thay schema, parser hay nội dung snapshot đã công bố của W3.
