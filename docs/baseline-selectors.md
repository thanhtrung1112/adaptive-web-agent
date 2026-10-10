# Baseline selectors (B0) cho MiniBiz v1

## 1. Selector / locator là gì
Để điều khiển trình duyệt, script phải chỉ rõ "phần tử nào trên trang". Chỉ dẫn đó là **selector** (Playwright gọi là **locator**). Hai dạng phổ biến:

| Dạng | Ý tưởng | Ví dụ trên MiniBiz |
|---|---|---|
| CSS | chọn theo `id`, `name`, thuộc tính | `#save-customer`, `table a[href='/orders/ORD-1003']` |
| XPath | chọn theo text hiển thị, label, quan hệ cấu trúc | `//button[normalize-space()='Lưu']`, `//label[normalize-space()='Email']/following-sibling::input[1]` |

## 2. Baseline B0 là gì
Baseline là **mốc so sánh** mà agent thích nghi phải thắng. B0 là script tự động hóa viết tay: mỗi bước (nhập ô, bấm nút, chọn dropdown) có một selector cố định, viết một lần trên giao diện gốc (M0). Selector **không tự sửa**: khi giao diện đổi và selector không còn khớp thì bước đó thất bại. Đó là hiện tượng "vỡ locator" mà đề tài giải quyết, nên không có B0 thì không có số liệu nào để nói agent tốt hơn bao nhiêu.

B0 được viết **hai bản tương đương** (CSS và XPath) cho mọi bước, vì chúng vỡ theo hai kiểu khác nhau:

| Mutation | CSS (id/name) | XPath (text/cấu trúc) |
|---|---|---|
| M1: đổi `id`, `class`, `name` | vỡ | thường còn sống |
| M2: đổi nhãn/text | còn sống | vỡ |
| M3: di chuyển node, thêm sibling | vỡ nếu dựa vị trí | vỡ nếu dựa `following-sibling`, chỉ số `[n]` |
| M4: đổi layout | gần như vỡ hết | gần như vỡ hết |

## 3. Cài đặt
- `baseline/scripts.py`: bảng `S` chứa cặp (CSS, XPath) cho từng phần tử; `SCRIPTS` mô tả T001-T010 bằng các bước `goto`, `fill`, `click`, `select`, `download`.
- `baseline/run_baseline.py`: chạy bằng Playwright ở chế độ `css`, `xpath` hoặc `both`. Mỗi task: reset database về `seed_v1` (gọi `app.seed.reset_database()`), mở browser context mới, chạy từng bước với timeout 3 giây, rồi chấm.
- `baseline/checker.py`: chấm theo `success_criteria` bằng JSON API (kiểm tra dữ liệu cuối, không đọc giao diện). API được gọi qua **chính browser context của task**, vì `/api/session/last_viewed_customer` (T002) phụ thuộc cookie phiên.
- Quy ước nghiêm: locator phải khớp đúng một phần tử (Playwright strict mode), không retry, không tự sửa, không dùng LLM.

## 4. Chạy
```bash
pip install -r requirements.txt
pip install playwright && playwright install chromium
python -m uvicorn app.main:app --port 8000          # terminal 1
python -m baseline.run_baseline --mode both          # terminal 2 (cùng thư mục repo)
```
Runner reset database trực tiếp nên phải chạy trong cùng thư mục repo với web. Kết quả ghi vào `runs/baseline_M0_<thời gian>/` (`results.csv`, `traces.json`, `summary.json`).

## 5. Kết quả (DOM gốc M0, 10 task pilot)
| Cấu hình | Thành công | Thời gian trung vị |
|---|---|---|
| B0-CSS | 10/10 | 0.42 s |
| B0-XPath | 10/10 | 0.38 s |

100% ở M0 là đúng kỳ vọng vì baseline viết trên chính DOM này; nó làm mốc trần để thấy mức tụt khi áp mutation.

Kiểm chứng bộ chấm phát hiện được lỗi thật: trên bản sao của app, đổi `id` hai nút và đổi nhãn hai nút rồi chạy T001, T006, T007:

| Cấu hình | Thành công | Task hỏng và lý do |
|---|---|---|
| B0-CSS | 1/3 | T001, T007 (đổi `id` nút) |
| B0-XPath | 1/3 | T006, T007 (đổi nhãn nút) |

Khớp với bảng mục 2: đổi `id` làm hỏng CSS, đổi nhãn làm hỏng XPath.

## 6. Giới hạn
- Chỉ có **10 task** (T001-T010), vì seed của app chỉ phục vụ pilot; mở rộng lên 20 task cần bổ sung seed và chức năng (tìm theo tên, sửa tên, số điện thoại tùy chọn...).
- Tìm khách hàng chỉ theo email đầy đủ, nên script dùng email.
- Chưa có B1 (Playwright `get_by_role`/`get_by_label`/`get_by_text`) và chưa có cơ chế mutation; phép thử ở mục 5 làm thủ công trên bản sao.
