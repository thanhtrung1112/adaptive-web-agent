# W5 — bộ mutation có phiên bản

Ngày 30/10/2026. Căn cứ bảng GVHD của KH1-N5, ô H45.

1. Tách namespace W5_ID/CLASS/TEXT/ORDER/STRUCTURE/COMBINED để giữ nguyên mode
   W4 và bằng chứng lịch sử. Tăng version benchmark thành 0.5.0.
2. Đổi thứ tự thực sự ở cột và điều hướng; giữ cặp header/cell và hàng colspan.
   Structure dùng wrapper hợp lệ, không đảo dòng hàng hóa hoặc ghép sai SKU/qty.
3. Class đổi cùng CSS tương đương. Không giữ class cũ trên node, không thêm thuộc
   tính original-id/target; giữ name để bảo toàn hợp đồng HTTP và JS.
4. Giữ snapshot schema 0.1. Validator chỉ mở rộng whitelist khi consumer truyền
   `mutation_modes` tường minh; mặc định W4 tiếp tục từ chối mode ngoài W4.
5. Ground truth/oracle chỉ thuộc evaluator. Không đổi cấu hình A1/A2 đã Accepted.
6. Development seeds 17/23; held-out W11 không được truy cập. Ghi rõ sự trùng
   biến thể có thể xảy ra vì order/structure có không gian hữu hạn.
7. Đóng gói full local dataset riêng; công bố mẫu cân bằng module/trục trên Git
   kèm toàn bộ kết quả tổng hợp và checksum. Không dùng mẫu để báo cáo full run.
