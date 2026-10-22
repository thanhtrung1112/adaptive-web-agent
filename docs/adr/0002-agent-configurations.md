# ADR-0002: Cấu hình baseline và agent cho benchmark

- Trạng thái: Accepted — Vũ Văn Bình và Nguyễn Thành Trung đã xác nhận ngày 2026-10-17.
- Ngày đề xuất: 17/10/2026.
- Ngày chấp thuận: 17/10/2026.
- Căn cứ: `docs/benchmark-spec.md`, mục 5.

## Bối cảnh

Benchmark cần các cấu hình đối chứng để phân biệt baseline locator, ranking dựa trên DOM và tác động của LLM fallback. W3 đã tích hợp candidate generator v0.1 trên snapshot, nhưng chưa có ADR ghi nhận cấu hình sẽ được đánh giá ở các tuần sau. PR #9 đã ghi nhận review xác nhận schema DOM snapshot v0.1; review này không thay cho quyết định cấu hình agent.

## Quyết định đề xuất

Giữ các cấu hình sau làm ma trận thí nghiệm, phù hợp với đặc tả benchmark hiện tại:

| Mã | Cấu hình | Vai trò |
|---|---|---|
| B0 | CSS/XPath viết tay trên DOM M0 | Baseline locator tĩnh đã đo ở W2. |
| B1 | Playwright semantic locator (`get_by_role`, `get_by_label`, `get_by_text`) | Baseline locator ngữ nghĩa, không dùng LLM. |
| A1 | Semantic DOM và candidate ranking dựa trên attributes, text, structure và embedding; không có LLM fallback | Đo khả năng xếp hạng khi locator gốc không còn phù hợp. |
| A2 | A1 cộng LLM fallback khi confidence thấp hoặc hành động thất bại | Đo phần đóng góp tăng thêm của LLM fallback. |

Candidate generator v0.1 hiện có trên W3 là nguyên mẫu ranking theo đặc trưng với trọng số thủ công. Kết quả snapshot-based của W3 không được xem là kết quả đầy đủ của A1; embedding, mutation trực tiếp trên app và A2 sẽ được triển khai/đánh giá theo lịch W4–W8.

## Hệ quả

- Báo cáo phải giữ riêng kết quả B0, B1, A1 và A2; không gộp thành một cấu hình.
- Các phép so sánh sau này phải dùng cùng tập task, mutation, success criteria và quy tắc tính chỉ số đã chốt trong benchmark spec.
- A2 chỉ gọi LLM theo điều kiện fallback được định nghĩa và log lại quyết định, số lần thử và token cost.
- Đề xuất hiện tại không thay đổi ADR-0001 về stack MiniBiz và cơ chế mutation.

## Phương án đã xét

- Chỉ giữ B0 và A1: không đo riêng giá trị của semantic baseline B1 hoặc tác động của LLM fallback.
- Gộp A1 và A2: không thể tách hiệu quả của candidate ranking khỏi LLM.
- Dùng LLM trong mọi lần chạy: làm tăng chi phí và khó xác định phần cải thiện do ranking.

## Cần nhóm xác nhận

- [x] Vũ Văn Bình xác nhận giữ cấu hình đề xuất.
- [x] Nguyễn Thành Trung xác nhận giữ cấu hình đề xuất.
- [x] Trạng thái cập nhật thành Accepted ngày 17/10/2026.
