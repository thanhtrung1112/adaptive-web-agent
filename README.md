# adaptive-web-agent

Đồ án: **Nghiên cứu và xây dựng AI Agent thích nghi tự động hóa tác vụ nghiệp vụ trên Web dựa trên mô hình ngôn ngữ lớn và phân tích DOM.**

Benchmark nội bộ (CRM / Order / Support) có nhiều phiên bản DOM/UI gây vỡ locator, dùng để so sánh selector truyền thống (CSS/XPath/Playwright) với agent dùng semantic DOM + LLM và self-healing.

## Cấu trúc
- `docs/`    Đặc tả benchmark, ADR, báo cáo tuần
- `tasks/`   Schema và danh sách task
- `scripts/` Script tiện ích

## Quy ước làm việc
- Mọi công việc gắn Issue; commit message có mã issue: `#12 feat: add customer form`.
- `main` được bảo vệ, merge qua Pull Request, review chéo giữa hai thành viên.
- Tag milestone: `v0.4` (W4), `v0.8` (W8), `v0.11` (W11), `v1.0` (W14).
- Dữ liệu lớn / model weights không commit vào Git; dùng Git LFS hoặc Drive/Model Hub, lưu checksum + manifest trong `data/manifest.json`.
- Thay đổi scope phải ghi ADR.

## Phạm vi và đạo đức
Chỉ chạy trên website thử nghiệm do nhóm sở hữu (synthetic app). Không tự động hóa website bên thứ ba.
