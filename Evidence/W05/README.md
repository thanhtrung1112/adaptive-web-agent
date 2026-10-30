# W5 — Nhóm KH1-N5 — Benchmark mutation 0.5.0

**Yêu cầu thầy:** “Tạo bộ mutation: đổi id/class/text/order/structure; version benchmark.”
Nguồn: bảng theo dõi 11 nhóm, sheet `Theo dõi 11 nhóm`, ô H45. Trích xuất/checksum
nguồn: [rubric.json](rubric.json). Thời gian tuần: 25–31/10/2026.

## Kết quả thực chạy

| Kiểm chứng | Kết quả | Nguồn |
|---|---|---|
| Hồi quy checkout phát triển | 85/85 tests | test-results.txt |
| Hồi quy W5 tách từ main | 63/63 tests | release-test-results.txt |
| Bảo toàn nghiệp vụ | 390/390 lượt; M0 30, mỗi mode W5 60 | results.csv, summary.json |
| Snapshot đầy đủ | 2.249 snapshot, schema 0.1 và hash HTML | validation.json |
| Cặp ground truth | 1.716 cặp đánh giá | validation.json |
| Hiệu lực mutation | 65 probe; cả năm trục phá locator M0 tương ứng | locator-probe.json |
| Phiên bản | 0.5.0; source/task/seed hash, mode/seed và chính sách tăng version | ../../data/benchmark_v0.5.0.json |

Kết quả oracle xác nhận nghiệp vụ CRM/Order/Support, bao gồm các task chain,
không phải tỷ lệ thành công của agent A1/A2 hoặc recovery. Probe nhận diện cả
locator không còn đích và locator vẫn khớp nhưng trỏ nhầm cột sau reorder.

## Đối chiếu sáu tiêu chí chấm

| Ô nguồn | Tiêu chí | Minh chứng / bước nghiệm thu |
|---|---|---|
| B46 | Submit đúng hạn (1đ) | Gói nộp đã chuẩn bị; thời điểm nộp LMS do thao tác thực tế quyết định |
| B47 | Đủ nội dung + evidence (2đ) | README, metrics.csv, log tests, figures, manifest, dataset mẫu và full dataset trong gói bàn giao |
| B48 | Deadline / deliverable (2đ) | Năm trục mutation, tổ hợp và version benchmark; báo cáo W5 và cập nhật Chương II |
| B49 | GitHub + phân chia (2đ) | Checklist Issue/PR, vai trò bàn giao, trạng thái thực trong manifest; cần review của hai thành viên |
| B50 | Chuyên môn / báo cáo (1đ) | Báo cáo phương pháp, protocol, kết quả, giới hạn, hướng dẫn tái lập |
| B51 | Chuyên môn riêng (2đ) | ID/class/text/order/structure có kiểm thử thực; benchmark 0.5.0 đóng băng bằng checksum |

Không tự điền điểm, không ghi đã nộp hoặc đã peer-review khi chưa có xác nhận.

## Phân công bàn giao

| Thành viên | Phần đề xuất nhận bàn giao và tự kiểm tra | Trạng thái |
|---|---|---|
| Vũ Văn Bình | Mutation implementation, context/JS, dữ liệu và nghiệp vụ | Đã có sản phẩm được chuẩn bị với Codex; chờ thành viên xác nhận |
| Nguyễn Thành Trung | Version benchmark, probe, kiểm tra hợp đồng ranking và tái lập | Đã có sản phẩm được chuẩn bị với Codex; chờ thành viên xác nhận/review |

Từng người cần Issue riêng, assignee đúng tài khoản, milestone Tuan5, link evidence;
PR có reviewer khác tác giả. Chỉ tag w05 trên commit đã tích hợp/review.
Mẫu nội dung: [docs/w5-github-handoff.md](../../docs/w5-github-handoff.md).

## Tái lập

Xem [hướng dẫn đầy đủ](../../docs/mutation-benchmark-v0.5.0.md).

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m w5.run --output runs/w5-reproduction --seeds 17 23
.\.venv\Scripts\python.exe -m w5.probe --output runs/w5-probe-reproduction
.\.venv\Scripts\python.exe scripts/build_w5_evidence.py --check
```

Full dataset ở `results/w5/benchmark_v0.5.0/` trong gói local; Git công bố mẫu
`results/w5/published_v0.5.0/` cùng kết quả tổng hợp đầy đủ và checksum.
Không suy rộng mẫu thành toàn bộ dataset. Seed 17/23 có thể trùng phép đổi order/
wrapper; kiểm thử riêng 17/18 bao phủ biến thể khác. Held-out W11 giữ riêng.
