# adaptive-web-agent

## Chạy MiniBiz Web App v1

Thực hiện từ thư mục repo có `app/` và `requirements.txt`. Dùng Python 3.13
(phiên bản đã kiểm thử); nếu `py` không khả dụng, dùng Python đã cài trên máy.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/reset_db.py --yes
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Mở http://127.0.0.1:8000. Các trang chính: `/customers`, `/orders`, `/tickets`.
Nhấn Ctrl+C để dừng server. Không tự reset khi server khởi động.
Lệnh reset xóa dữ liệu chạy thử và khôi phục 4 khách, 2 sản phẩm, 5 đơn,
2 nhân viên, 2 ticket. Dừng server trước reset; mỗi task dùng browser context mới.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts/validate_tasks.py
```

Kiểm thử dùng database tạm, không ghi vào database đang dùng. Cảnh báo deprecation
từ TestClient/httpx có thể xuất hiện; đọc kết quả OK/FAILED để biết trạng thái kiểm thử.
Hướng dẫn đối chiếu T001–T010: [Bàn giao app v1](docs/app-v1-handoff.md).

App v1 hiện phục vụ DOM gốc M0. Chưa bao gồm mutation, baseline trình duyệt,
bộ 20 task hoặc LLM/self-healing. Các kiểm thử tích hợp không phải số liệu benchmark.

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
