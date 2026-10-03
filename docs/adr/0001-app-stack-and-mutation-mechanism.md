# ADR-0001: Stack của MiniBiz và cơ chế mutation

- Trạng thái: Đề xuất (cần hai thành viên xác nhận)
- Ngày: 2026-10-02

## Bối cảnh
Benchmark cần một app nghiệp vụ nhỏ sinh được nhiều phiên bản DOM tái lập, dễ chạy trong Docker và với Playwright.

## Quyết định
1. Backend: FastAPI + Jinja2 (server-side rendering), SQLite cho dữ liệu app, JSON API `/api/*` để chấm success criteria.
2. Mutation thực hiện ở lớp template qua tham số `mutation` và `seed` (không có nhiều app riêng).
3. Mỗi mutation là một hàm biến đổi thuần, có kiểm thử đảm bảo chức năng không đổi.

## Lý do
- SSR giữ DOM ổn định, dễ snapshot, ít nhiễu hơn SPA nên đo mutation chính xác hơn.
- Một app nhiều mutation giúp tái lập và giảm công bảo trì.
- Cùng ngôn ngữ Python với agent và harness, giảm chi phí tích hợp.

## Hệ quả
- Không đánh giá được hành vi đặc thù SPA (virtual DOM, lazy render); ghi vào phần giới hạn của báo cáo.
- Có thể thêm một trang SPA nhỏ ở giai đoạn stretch.

## Phương án đã xét
Flask (tương đương, ít tiện ích kiểu dữ liệu hơn); React SPA (thực tế hơn nhưng DOM biến động, khó kiểm soát nhiễu).
