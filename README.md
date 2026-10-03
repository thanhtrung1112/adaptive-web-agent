# adaptive-web-agent

Đồ án: **Nghiên cứu và xây dựng AI Agent thích nghi tự động hóa tác vụ nghiệp vụ trên Web dựa trên mô hình ngôn ngữ lớn và phân tích DOM.**

Benchmark nội bộ (CRM / Order / Support) có nhiều phiên bản DOM/UI gây vỡ locator, dùng để so sánh selector truyền thống (CSS/XPath/Playwright) với agent dùng semantic DOM + LLM và self-healing.

## Trạng thái
| Tuần | Nội dung | Trạng thái |
|---|---|---|
| W1 (27/09-03/10) | Benchmark spec, repo, 10 pilot tasks | Hoàn thành bản v0.1 |
| W2 (04/10-10/10) | Web app v1 + baseline selectors | Chưa bắt đầu |

## Cấu trúc
```
docs/benchmark-spec.md        Đặc tả benchmark (app, task, mutation, metric, protocol)
docs/adr/                     Architecture Decision Records
docs/weekly/                  Weekly Evidence Package (Planned-Done-Evidence-Problems-Next)
docs/github-setup.md          Lệnh tạo milestone/issue/branch protection
tasks/task_schema.json        JSON Schema cho một task
tasks/pilot_tasks.json        10 pilot tasks (W1)
scripts/validate_tasks.py     Kiểm tra tasks theo schema + ràng buộc nhất quán
```

## Quy ước làm việc
- Mọi công việc gắn Issue; commit message có mã issue: `#12 feat: add customer form`.
- `main` được bảo vệ, merge qua Pull Request, review chéo giữa hai thành viên.
- Tag milestone: `v0.4` (W4), `v0.8` (W8), `v0.11` (W11), `v1.0` (W14).
- Dữ liệu lớn / model weights không commit vào Git; dùng Git LFS hoặc Drive/Model Hub, lưu checksum + manifest trong `data/manifest.json`.
- Thay đổi scope phải ghi ADR.

## Chạy kiểm tra
```bash
pip install -r requirements.txt
python scripts/validate_tasks.py
```

## Phạm vi và đạo đức
Chỉ chạy trên website thử nghiệm do nhóm sở hữu (synthetic app). Không tự động hóa website bên thứ ba.
