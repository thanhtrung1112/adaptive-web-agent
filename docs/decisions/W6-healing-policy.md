# ADR W6-B: Chính sách chọn lại phần tử (healing) và bỏ cuộc

Trạng thái: **đề xuất**, chờ review của thành viên còn lại. Đổi tên file theo quy ước đánh số ADR của repo khi merge.

## Bối cảnh
Khi locator B0 hỏng, agent cần chọn lại phần tử trên trang đã đổi. Chọn nhầm có thể gây thao tác sai (thất bại ngầm), tệ hơn dừng lại. Các dòng lặp trong form đơn hàng làm hai ứng viên có điểm gần bằng nhau; ở W4, `rank` xử lý hòa bằng thứ tự DOM, nên kết quả phụ thuộc vị trí.

## Quyết định
1. **Chế độ mặc định của W6:** `features` (điểm đặc trưng W3), không dùng embedding.
2. **Bỏ cuộc** khi hạng 1 hơn hạng 2 ít hơn `min_margin = 0,02` (giá trị đặt trước, chưa tinh chỉnh trên dữ liệu). API mặc định dùng ngưỡng này và `use_order=False`; đối chứng đoán theo thứ tự DOM phải truyền tường minh `min_margin=0.0, use_order=False`.
3. **Tie-break theo thứ tự dòng** khi gần hòa và bật `use_order=True`: chỉ nhận ứng viên **duy nhất** cùng nhóm `(tag, type, form)` và cùng `ord`, `ord_n` với descriptor; số dòng lặp đã đổi hoặc vẫn mơ hồ thì bỏ cuộc (`ambiguous_order`). Ứng viên được chọn phải đạt `min_score`, nếu không bỏ cuộc (`low_score`).
4. `heal()` chỉ nhận **descriptor và ứng viên**; `element_id`, `target_element_id`, `ref_eid` không được truyền vào (chỉ dùng để chấm).
5. Mỗi lần gọi trả về `status`, `reason`, `via`, `top1_eid`, `topk` để ghi log; luôn ghi tỷ lệ **chữa nhầm** riêng với tỷ lệ bỏ cuộc.

## Phương án đã cân nhắc
| Phương án | Lý do không chọn |
|---|---|
| Hòa thì lấy theo thứ tự DOM (cấu hình A) | Phụ thuộc vị trí trang; chữa nhầm 4 lượt `W5_COMBINED` (và 18 lượt ở mô phỏng) |
| Luôn bỏ cuộc khi gần hòa (cấu hình B) | An toàn nhưng bỏ cuộc 12 lượt mà thứ tự dòng giải được |
| `hybrid` với encoder hash (cấu hình D) | Kém features: 2 nhầm, 9 bỏ cuộc trên 1.716 cặp; chưa thử sbert |
| Điểm đặc trưng cố định theo vị trí hàng/cột | Dễ vỡ khi thêm hoặc bớt dòng; cần `ord_n` để từ chối |

## Hệ quả
- Trên 1.716 cặp W5 (hai seed phát triển) cấu hình C: 1.716 đúng, 0 nhầm, 0 bỏ cuộc. Đây là kết quả offline, **không** phải recovery của agent.
- Số `W5_ORDER` (83% trùng giữa hai seed) và `W5_STRUCTURE` (50%) phải báo cáo theo biến thể duy nhất.
- Ngưỡng `0,02` và α chưa được chọn trên dev; việc này để W7. Nếu đổi giá trị mặc định, ghi ADR mới.
- Giới hạn đã biết: chưa kiểm `wrong_target`, chưa có B0 online, nhiễu `id`/`name` ngẫu nhiên gây 5 ca nhầm ở mô phỏng `combined`.

## Phạm vi
ADR này chỉ quy định chính sách chọn lại phần tử. Việc **khi nào gọi** `heal()` (chỉ khi B0 hỏng, hay luôn xác minh) thuộc ADR-W6-A của luồng online.
