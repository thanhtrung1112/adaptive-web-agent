# Evidence W06 — Online self-healing, phần Bình

Theo bàn giao A1–A6: đóng băng mutation set, record B0, conditional healing,
390 lượt, demo và chính sách gọi heal. Hướng dẫn: `docs/w6-online-healing.md`;
báo cáo: `docs/weekly/W6.md`; quyết định: `docs/decisions/W6-online-trigger-policy.md`.

## Kết quả

- Record: 30/30 task M0, 143 descriptor; nguồn sạch ở commit `61baf8a`.
- Online: **390/390** lượt đạt API/CSV; **120/120** task có healing phục hồi thành công.
- 500 healing attempts, 500 thao tác hoàn tất; 0 abstention trong ma trận.
- Kiểm thử: **109 tests + 608 subtests pass**, 1 cảnh báo Starlette deprecation.
- Demo: T004/T010 trên COMBINED, seed 17/18, **4/4** lượt đạt.
- Không LLM hoặc oracle target mapping trong runner. Held-out W11 chưa truy cập.

## Chỉ mục

- `online/mutation-set-v1.json`: bản manifest đã dùng, gồm hash mã và audit seed.
- `online/metadata.json`: commit, nguồn, policy, phiên bản browser/thư viện.
- `online/results.csv`, `summary.json`: toàn bộ ma trận.
- `online/traces/`: 390 trace JSON theo task/mode/seed.
- `online/snapshots/`: DOM/feature JSON tại thời điểm gọi healing.
- `online/record/`: metadata, 143 descriptor, 30 trace M0 và snapshot trước thao tác.
- `online/demo/`: trace, ảnh, metadata demo; video được đóng gói riêng local.
- `online/validation.json`, `checksums.json`: kiểm tra integrity/coverage và hash artifact.
- `test-results.txt`: log hồi quy thực chạy trên môi trường `.venv`.

```powershell
.\.venv\Scripts\python.exe -m w6.evidence --verify Evidence/W06/online
```

Recovery ở đây tính cấp task. Không có nhãn đích độc lập thì số chữa nhầm online
giữ `null`; 500 action success không đồng nghĩa 500 nhãn chọn đích đúng độc lập.
CSS không bị phá ở bốn mode, nên 100% task pass không chứng minh healing được
kích hoạt ở cả sáu mode. Chưa xử lý B0 khớp đúng một phần tử nhưng sai đích.

Trạng thái: implementation và evidence local đã có; chờ Trung review, merge và
xác nhận nộp LMS. Có hỗ trợ Codex; không tự xác nhận review, điểm hoặc nộp đúng hạn.
