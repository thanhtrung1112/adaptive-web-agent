# Semantic locator ranking v0.1 (W4, phần 2)

## Mục đích
Xếp hạng các control ứng viên của trang mới theo độ giống với phần tử gốc, kết hợp **điểm đặc trưng** của candidate generator (W3) với **độ giống embedding** (cosine). Đây là embedding baseline của W4; LLM fallback (W5-W6) nhận danh sách này.

## Thành phần
| File | Vai trò |
|---|---|
| `ranking/text.py` | Biến một control thành câu ngắn, ví dụ `nút Lưu; trong biểu mẫu /customers/new` |
| `ranking/encoders.py` | `HashingEncoder` (offline, chỉ bắt giống về mặt chữ) và `SentenceTransformerEncoder` (embedding ngữ nghĩa, mặc định `paraphrase-multilingual-MiniLM-L12-v2`); có cache theo chuỗi |
| `ranking/rank.py` | Ba chế độ: `features` (= generator v0.1), `embedding` (chỉ cosine), `hybrid` = alpha × đặc trưng + (1 − alpha) × cosine |
| `ranking/stress.py` | Kịch bản khó hơn W3 trên snapshot mô phỏng: `flatten` (mất thông tin form và vị trí trong cây) và `hard` (id + nhãn đồng nghĩa + nút mồi + flatten) |
| `ranking/evaluate.py` | Đánh giá trên **snapshot mô phỏng** (79 phần tử đích); chia dev/test theo trạng thái trang |
| `ranking/evaluate_w4.py` | Đánh giá trên **mutation thật M1-M3** (429 cặp); chia dev/test theo task |

## Chạy
```bash
pip install -r requirements.txt -r requirements-ranking.txt

# Mutation thật W4 
python -m ranking.evaluate_w4 --dataset runs/w4-trung-full --encoder hash  --out out_hash.json
python -m ranking.evaluate_w4 --dataset runs/w4-trung-full --encoder sbert --out out_sbert.json

# Mô phỏng 
python -m ranking.evaluate --encoder hash
python -m ranking.evaluate --encoder sbert
```
Kết quả đã lưu: `results/w4/ranking_w4_{hash,sbert}_full/evaluation.json` (mutation thật) và `results/w4/ranking_{hash,sbert}_v0.1/evaluation.json` (mô phỏng).

## Dữ liệu
- **Dataset thật:** `runs/w4-trung-full` do `python -m w4.run --seeds 7` sinh ra, commit nguồn `788762a`, seed dữ liệu `seed_v1`, **seed mutation phát triển 7**, 30 task (T001-T030) × M0-M3. 120/120 lượt replay qua kiểm tra chức năng bằng evaluation oracle (oracle biết quy tắc mutation; đây **không** phải tỷ lệ thành công của B0 hay embedding). 692 snapshot, **429 cặp** (trước, sau) có ground truth.
- Thư mục dataset (32 MB) **không đưa vào Git**; lưu ngoài repo, ghi `sha256` ở chỗ nộp. Mẫu nhỏ nằm ở `results/w4/binh_v1/` dùng cho test.
- **Không dùng held-out** (để dành cho W11).
- Định nghĩa mutation theo `docs/w4-binh-handoff.md`:

| Mức | Biến đổi thực tế trong v1 |
|---|---|
| M1 | Đổi **id** (băm FNV-1a + seed), cập nhật `for`/ARIA/fragment. **Chưa** đổi class, name, data-* (spec nêu rộng hơn) |
| M2 | Đổi nhãn/nút/link/placeholder theo bảng từ đồng nghĩa cố định + seed |
| M3 | Bọc 1 hoặc 2 `span` (`display:contents`) quanh control |

## Kết quả trên mutation thật (429 cặp, 143 cặp mỗi mức)
Định dạng: top-1 / top-3 / MRR. Chế độ `features` và `hybrid` đạt 1,000 / 1,000 / 1,000 ở **mọi** mức, mọi encoder, trên cả tập test lẫn toàn bộ.

**Chế độ `embedding`, toàn bộ 429 cặp:**

| Mức | hash | sbert |
|---|---|---|
| M1 | 0,972 / 1,000 / 0,986 | 0,972 / 1,000 / 0,986 |
| M2 | 0,951 / 0,979 / 0,970 | 0,881 / 1,000 / 0,931 |
| M3 | 0,972 / 1,000 / 0,986 | 0,972 / 1,000 / 0,986 |
| Chung | 0,965 / 0,993 / 0,981 | 0,942 / 1,000 / 0,968 |

**Chế độ `embedding`, chỉ tập test (123 cặp, 41 cặp mỗi mức):**

| Mức | hash | sbert |
|---|---|---|
| M1 | 0,951 / 1,000 / 0,976 | 0,951 / 1,000 / 0,976 |
| M2 | 0,951 / 1,000 / 0,976 | 0,854 / 1,000 / 0,919 |
| M3 | 0,951 / 1,000 / 0,976 | 0,951 / 1,000 / 0,976 |
| Chung | 0,951 / 1,000 / 0,976 | 0,919 / 1,000 / 0,957 |

Hybrid dùng α chọn trên dev: 0,25 (hash), 0,5 (sbert).

**Lưu ý về α.** MRR trên dev theo α (file `evaluation.json`): hash {0: 0,983; 0,25 / 0,5 / 0,75 / 1,0: 1,000}; sbert {0: 0,972; 0,25: 0,990; 0,5 / 0,75 / 1,0: 1,000}. Nhiều α cho MRR bằng nhau, và luật hòa chọn α nhỏ nhất; do đó **α không phải kết quả đo được**, chỉ là giá trị mặc định của luật hòa.

## Cách đọc kết quả
- **Features đạt trần (1,000) nên chưa phân biệt được các phương pháp.** Mỗi mutation M1-M3 chỉ làm đổi một nhóm đặc trưng (M1: id; M2: chữ; M3: cấu trúc), các nhóm còn lại giữ nguyên và đủ để định vị. Hybrid không hơn features vì features đã đạt trần, không phải vì embedding vô dụng.
- **Embedding thuần đạt thấp hơn features** ở cả hai encoder. Phần lớn lỗi đến từ ca hòa điểm, không phải sai ngữ nghĩa (xem dưới).
- Ranker nhận `(descriptor, candidates)` từ `w4.dataset.ranking_inputs`; `target_element_id` chỉ đọc **sau** khi ranker trả kết quả.

## Phân tích lỗi embedding
Có 15 ca chưa hạng 1 với hash và 25 ca với sbert (tất cả thuộc chế độ `embedding`). Phân tích thủ công dựa trên `misses` trong `evaluation.json` và dataset (**chưa có script trong repo**, xem "Việc tiếp theo"):

| Nhóm | Mô tả | Số ca |
|---|---|---|
| Hòa điểm do câu trùng | Hai control có câu mô tả giống hệt (các dòng lặp của form đơn hàng). Hòa thì giữ thứ tự DOM, nên kết quả phụ thuộc vị trí. Chỉ gồm **4 bước task** (T004, T024; mỗi task 2 bước), lặp ở M1-M3 | 12 cặp (4 ở mỗi mức); là **toàn bộ** lỗi M1 và M3 của cả hai encoder |
| Lỗi thật ở M2 | Nhãn đổi bị chọn nhầm | hash 3 cặp, sbert 13 cặp |

Các lỗi thật ở M2 của sbert thuộc **4 phép đổi nhãn khác nhau**, lặp qua nhiều task: "Sửa → Cập nhật thông tin" (hash cũng sai), "Tạo đơn → Tạo đơn hàng mới", "Thêm dòng → Thêm sản phẩm", "Đến ngày (UTC) → Ngày kết thúc (UTC)". Với ca cuối, sbert chọn nhầm nhãn đối ứng "Từ thời điểm (UTC)".

## Kết quả mô phỏng (79 phần tử đích: 52 dev, 27 test)
Top-1 trên tập test, α chọn trên dev. Chỉ dùng để kiểm tra đường ống; biến đổi là mô phỏng trên snapshot.

| Kiểu đổi | features | embedding hash | hybrid hash | embedding sbert | hybrid sbert |
|---|---|---|---|---|---|
| không đổi / đổi id | 1,000 | 1,000 | 1,000 | 1,000 | 1,000 |
| flatten | 1,000 | 1,000 | 1,000 | 0,963 | 1,000 |
| đổi nhãn | 1,000 | 0,741 | 1,000 | 0,741 | 1,000 |
| tổ hợp id + nhãn + lớp bọc | 1,000 | 0,741 | 1,000 | 0,741 | 0,963 |
| hard | 0,889 | 0,704 | 0,889 | 0,630 | 0,963 |

Mỗi chênh lệch nhỏ (0,037) tương ứng đúng **1 phần tử** trong 27; chưa có ý nghĩa thống kê.

## Hạn chế
- **Số mẫu độc lập nhỏ.** 143 cặp mỗi mức không độc lập: M1/M2/M3 của cùng task chung bước, các task cùng mẫu lặp nhãn. M2 chỉ có 50 phép đổi nhãn (gốc → sau) khác nhau trên 125 cặp có nhãn thực sự đổi. Chênh lệch hash và sbert ở M2 vì vậy chưa kết luận được.
- **Chưa đủ khó.** Mutation M1-M3 mỗi lần chỉ phá một nhóm đặc trưng; chưa có M4 (kết hợp) trên mutation thật.
- **Độ trễ trong JSON không đáng tin** (encoder cache theo chuỗi, α chọn trước khi đo). Không dùng để so sánh tốc độ.
- **Dev/test chỉ bảo vệ việc chọn α**, không bảo vệ thiết kế features và mutation (cùng nhóm phát triển, cùng seed 7).
- Chỉ một mô hình sbert (`paraphrase-multilingual-MiniLM-L12-v2`); chưa so sánh mô hình thứ hai.
- Mẫu câu trong `ranking/text.py` và lưới α (0; 0,25; 0,5; 0,75; 1) chọn tay. Giả thuyết tiền tố "nút/liên kết" và hậu tố "trong biểu mẫu" chiếm phần lớn cosine **chưa được kiểm chứng**.
- Số hash đã được chạy lại độc lập (khớp file lưu); số sbert lấy từ lần chạy trên máy nhóm, **chưa tái lập độc lập**.
- Phần phân tích có hỗ trợ AI (viết mã, review); người nộp chịu trách nhiệm kiểm lại.

## Việc tiếp theo
1. Thêm `ranking/analyze_misses.py`: phân loại ca hòa và lỗi thật từ `misses`.
2. Thêm metric tính ca hòa (lạc quan, bi quan, kỳ vọng) và test ẩn danh `element_id`.
3. Thêm M4 (kết hợp) hoặc stress kết hợp trên dữ liệu thật; so sánh ít nhất hai mô hình `--model`.
4. Đo độ trễ riêng (xóa cache, đo `encode` riêng).
5. Ablation `element_text` (bỏ tiền tố loại control, bỏ "trong biểu mẫu").
6. Ghi commit của mã ranking vào `evaluation.json`; đóng băng mã trước W11.
