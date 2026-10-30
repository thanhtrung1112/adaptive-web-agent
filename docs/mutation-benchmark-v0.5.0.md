# Bộ mutation và benchmark 0.5.0 — W5

## Yêu cầu và phạm vi

Nhóm KH1-N5, Vũ Văn Bình và Nguyễn Thành Trung. Bảng GVHD, sheet `Theo dõi 11 nhóm`,
ô H45: **Tạo bộ mutation: đổi id/class/text/order/structure; version benchmark.**
W5: 25–31/10/2026. Nguồn trích, vị trí ô và SHA-256: `Evidence/W05/rubric.json`.

Một MiniBiz duy nhất sinh HTML khác nhau ở render boundary. Không sửa snapshot để
giả lập mutation, không sửa các ADR Accepted hoặc thay đổi hành vi M0–M3 của W4.
Các mode W5 có namespace riêng và có thể mở trực tiếp:

```text
http://127.0.0.1:8000/customers?mutation=W5_COMBINED&seed=17
```

## Năm trục và biến thể kết hợp

| Mode | Thao tác thực sự trên HTML | Bất biến cần giữ |
|---|---|---|
| M0 | HTML gốc | Đối chứng |
| W5_ID | ID băm FNV-1a 64-bit theo seed; sửa IDREF, `for`, fragment | Label vẫn liên kết; dòng Order động có ID duy nhất |
| W5_CLASS | Đổi từng class token; đổi tên `data-*` nếu có | CSS tương đương được tạo cùng tên class mới; không lộ bản đồ ID gốc |
| W5_TEXT | Nhãn, button, link, placeholder và aria-label theo từ điển đồng nghĩa | Giữ giá trị option và dữ liệu nghiệp vụ |
| W5_ORDER | Xoay thứ tự cột đồng bộ giữa header và các hàng; xoay link điều hướng | Giữ khớp cột–giá trị; giữ thứ tự bản ghi và các hàng colspan |
| W5_STRUCTURE | Thêm 1 hoặc 2 span wrapper theo parity của seed | HTML hợp lệ; giữ label, form, table/option và hành vi JS |
| W5_COMBINED | ID → text → structure → class → order | Tất cả các bất biến trên |

Tên `name` phục vụ truyền dữ liệu form, action/href nghiệp vụ và option value được
giữ nguyên. Tiêu chí W5 không bắt buộc đổi `name`. W5_COMBINED là tổ hợp của năm
trục W5, chưa triển khai M4 layout hoặc thay thế bộ held-out W11.

Cookie context riêng mỗi browser giữ mutation và seed qua GET, POST, redirect và
form lỗi. Các API chỉ đọc và tệp CSS gốc không bị sửa. `orders.js` tính ID mới cho
dòng clone bằng cùng thuật toán Python, không dùng ID đáp án gắn thêm vào DOM.

## Phiên bản và cách chạy lại

Phiên bản đóng băng: `data/benchmark_v0.5.0.json`, gồm task/seed/source checksum,
tập mode, seed phát triển và chính sách version. Giữ task T001–T030, data seed_v1,
success criteria và checker hiện có. Thay đổi transformation/task/checker/seed set
phải tăng phiên bản; không ghi đè kết quả 0.5.0.

Từ thư mục repo, sau khi cài `requirements.txt` và Chromium của Playwright:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m w5.run --output runs/w5-reproduction --seeds 17 23
.\.venv\Scripts\python.exe -m w5.probe --output runs/w5-probe-reproduction
.\.venv\Scripts\python.exe scripts/build_w5_evidence.py --check
```

Runner từ chối thư mục output đã tồn tại. Mỗi task reset database tạm, browser
context mới, kiểm tra success criteria chưa đạt trước thao tác và chấm kết quả
bằng API/CSV. M0 chạy một lần/task; mỗi mode W5 chạy hai seed 17/23: tổng
`30 × (1 + 6 × 2) = 390` lượt. Không đọc/sinh held-out W11.

`w5.run.oracle` chỉ dùng ở evaluator để tìm đích và tạo ground truth. Ranker chỉ
nhận descriptor/candidates theo `w4.dataset.ranking_inputs`. Không xem oracle
pass rate là tỷ lệ thành công của A1/A2 hoặc self-healing. W6 của bảng GVHD
mới yêu cầu xây self-healing selector bằng DOM + similarity.

## Minh chứng và diễn giải

- `Evidence/W05/summary.json`, `results.csv`: toàn bộ ma trận chức năng.
- `Evidence/W05/test-results.txt`: log hồi quy thực chạy, gồm regression W4 và W5.
- `Evidence/W05/locator-probe.json`: 65 phép kiểm tra năm locator cố định từ M0.
- `Evidence/W05/figures/`: ảnh browser của từng mode/seed.
- `results/w5/published_v0.5.0/`: bộ mẫu JSON/HTML hoàn chỉnh cho CRM/Order/Support.
- `results/w5/benchmark_v0.5.0/`: dataset đầy đủ local, đưa kèm gói bàn giao riêng.
- `Evidence/W05/manifest.json`: checksum artifact và trạng thái bàn giao GitHub.

Probe kiểm tra đúng **danh tính đích**, không chỉ `count() > 0`. Đổi cột có thể vẫn
khớp nth-child nhưng trỏ sai ý nghĩa. Năm probe này minh chứng mutation có hiệu
lực, không phải ma trận task success đầy đủ của B0. Không suy rộng 30 task biến
thể thành 30 workflow độc lập hoặc kết luận robustness trên Web nói chung.

Seed khác nhau không đảm bảo mọi trục tạo DOM khác nhau: wrapper có hai độ sâu,
order có số hoán vị hữu hạn; seed 17 và 23 có thể trùng ở các trục này. Kiểm thử
17/18 riêng xác nhận nhánh thay đổi thứ tự/độ sâu. Hai seed là hai cấu hình chạy,
không được coi là hai mẫu thống kê độc lập ở mọi trục.

## Phân công bàn giao và review

Đề xuất Bình kiểm tra implementation mutation, context và dữ liệu; Trung kiểm
tra version, frozen locator probes, hợp đồng ranking và tái lập. Bộ mã/bằng chứng
được chuẩn bị với hỗ trợ Codex trong phiên làm việc này; chưa dùng tài liệu này
để khẳng định hai thành viên đã tự review hoặc đã được GVHD nghiệm thu.

Mỗi thành viên cần Issue riêng liên kết evidence, một PR W5, milestone Tuan5 và
review của thành viên còn lại. Chỉ gắn tag `w05` sau khi tích hợp và review xong.
Điểm, nộp đúng hạn và review thực tế phải phản ánh thao tác thực trên GitHub/LMS.
