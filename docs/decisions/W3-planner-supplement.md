# Bổ sung W3 theo lịch đánh giá mới

Ngày 24/10/2026, người dùng cung cấp lịch W3: agent hiểu yêu cầu và lập kế hoạch browser;
W4: DOM/semantic matching; W5: mutation. File đề cương cũ đặt planner/executor ở W5.
Ghi nhận điều chỉnh lịch, không sửa ADR-0001/0002 Accepted hoặc bằng chứng lịch sử.

Triển khai planner độc lập với tầng chọn locator. Việc gọi LLM cho planning không phải
LLM fallback của A2; các benchmark B0/B1/A1/A2 hiện tại chưa thay đổi. Khi tích hợp cần
chốt cùng plan đầu vào cho so sánh locator, hoặc ghi riêng chi phí và chất lượng planner.

Dùng Ollama local đã có trên máy, không cài/thay môi trường, không mua API. Chưa có lựa
chọn mô hình chính thức của nhóm; qwen2.5:latest chỉ dùng kiểm chứng prototype. Chưa tuyên
bố W3 hoàn tất nếu kế hoạch sai nghiệp vụ hoặc chưa được review theo tiêu chí của thầy.

Planner schema 0.2 dùng verification riêng bắt buộc, thay prototype 0.1 yêu cầu step verify cuối.
Giữ trace cũ làm lỗi phát triển, không sửa số liệu hoặc dùng như kết quả schema 0.2.

## Quyết định bổ sung ngày 28/10/2026

Theo yêu cầu người dùng triển khai planner kết hợp: LLM trích intent có source span;
quy trình MiniBiz dựng bước và validator kiểm tra tiền điều kiện/dữ liệu. Không tự
tuyên bố LLM sinh mọi bước, không dùng task ID/baseline scripts để dựng plan.
Giữ plan 0.2 và DOM 0.1; thêm hợp đồng intent 1.0/workflow 1.0 cho consumer mới.
Qwen3.5:4b local với think=false dùng thử; quyết định model chính thức còn phụ thuộc
review kết quả. Harness M0 bằng accessibility adapter cố định chỉ đo tính khả thi,
không thay thế semantic ranking hoặc benchmark recovery. Không sửa ADR Accepted.
Hướng dẫn: docs/planner-hybrid-w3.md.
