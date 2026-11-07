# W6: Self-healing selector bằng DOM + similarity (luồng offline, phần Trung)

## Mục đích
Khi locator B0 hỏng (không tìm thấy, hoặc tìm trúng nhiều phần tử), chọn lại phần tử đúng trên trang đã đổi bằng đặc trưng DOM và độ giống, **không dùng LLM**, và **bỏ cuộc** khi không đủ chắc. Tài liệu này mô tả lõi `healing/` và đánh giá offline trên dataset benchmark 0.5.0.

Phạm vi: đo **độ chính xác chọn lại phần tử** trên các cặp (trang M0, trang đã mutate) có ground truth. Đây **không** phải tỷ lệ thành công hay recovery của agent chạy thật (chưa có runner online, chưa có B0 trên mutation W5).

## Thành phần
| File | Vai trò |
|---|---|
| `healing/descriptor.py` | `build_descriptor(snapshot, eid)`: 11 đặc trưng của phần tử mà B0 trỏ tới ở M0, kèm `ord`, `ord_n`; không chứa `element_id` hay `xpath`. `controls_with_xpath(snapshot)`: control của trang mới kèm `xpath` |
| `healing/heal.py` | `heal(descriptor, cands, mode, min_margin, min_score, use_order, ...)`: chọn phần tử hoặc bỏ cuộc (`low_margin`, `low_score`, `no_candidates`, `ambiguous_order`) |
| `healing/ordinal.py` | `ord` (vị trí trong nhóm cùng thẻ, type, form) và `ord_n` (kích thước nhóm) để phân biệt dòng lặp |
| `healing/eval_order.py` | Đo tie-break thứ tự dòng trên biến đổi mô phỏng của snapshot M0 |
| `healing/evaluate.py` | Đánh giá offline trên dataset có `ground_truth/pairs.json` (4 cấu hình) |
| `tests/test_healing.py` | 13 test |

Điểm lấy từ `ranking.rank` (W3/W4), làm tròn 3 chữ số, nên margin có độ phân giải 0,001. Hòa điểm không được quyết bằng thứ tự DOM trừ cấu hình A.

## Cấu hình đánh giá
| Cấu hình | Mô tả |
|---|---|
| A | `features`, hòa thì lấy hạng đầu theo thứ tự DOM (hành vi W4) |
| B | `features`, bỏ cuộc khi margin < 0,02 |
| C | `features`, margin < 0,02 thì dùng thứ tự dòng (`use_order`); từ chối nếu `ord_n` đổi |
| D | `hybrid` (encoder hash, α = 0,25) + thứ tự dòng |

Ngưỡng `min_margin = 0,02` và α = 0,25 là **giá trị đặt trước** (α lấy từ dev của W4), **chưa tinh chỉnh trên dữ liệu W6** (việc chọn ngưỡng trên dev để lại cho W7).

## Dữ liệu
- Dataset sinh lại: `python -m w5.run --output runs/w5-reproduction --seeds 17 23`, benchmark 0.5.0, 30 task × (M0 + 6 mode × 2 seed), **chỉ seed phát triển 17 và 23**, không dùng held-out W11.
- 1.716 cặp (6 mode × 286), 2.249 snapshot (theo `summary.json` của W5).
- SHA-256: `runs/w5-reproduction/ground_truth/pairs.json` = `A026F5B83DF6A2F2C16FBE86E17DF684983A3771E93683E1CE4EE5C380CA541B`; `metadata.json` = `96D4102C724B7BC08F816366E4787173508C5E0634406842CFE4798AF4720E5B`. Dataset đầy đủ **không đưa vào Git**; commit nguồn: `<điền commit>`.
- Ground truth (`target_element_id`) chỉ dùng để chấm; không đi vào `heal()`.

## Kết quả: 1.716 cặp, định dạng đúng / nhầm / bỏ cuộc
Mỗi mode có 286 lượt (143 bước × 2 seed). Cột phải loại seed trùng biến thể.

**Biến thể HTML giống hệt giữa hai seed (cùng task, bước, mutation):**
| Mode | Nhóm trùng | Số biến thể duy nhất |
|---|---|---|
| `W5_ORDER` | 119/143 | 167 |
| `W5_STRUCTURE` | 72/143 | 214 |
| ID, CLASS, TEXT, COMBINED | 0/143 | 286 |

**Tất cả lượt (mọi seed):**
| Mode | A | B | C | D |
|---|---|---|---|---|
| `W5_CLASS` | 286 / 0 / 0 | 286 / 0 / 0 | 286 / 0 / 0 | 286 / 0 / 0 |
| `W5_COMBINED` | 282 / **4** / 0 | 278 / 0 / 8 | **286 / 0 / 0** | 278 / **2** / 6 |
| `W5_ID` | 286 / 0 / 0 | 282 / 0 / 4 | 286 / 0 / 0 | 286 / 0 / 0 |
| `W5_ORDER` | 286 / 0 / 0 | 286 / 0 / 0 | 286 / 0 / 0 | 286 / 0 / 0 |
| `W5_STRUCTURE` | 286 / 0 / 0 | 286 / 0 / 0 | 286 / 0 / 0 | 286 / 0 / 0 |
| `W5_TEXT` | 286 / 0 / 0 | 286 / 0 / 0 | 286 / 0 / 0 | 283 / 0 / 3 |

**Biến thể duy nhất:** giống cột trên, chỉ khác `W5_ORDER` (167 lượt) và `W5_STRUCTURE` (214 lượt), kết quả mỗi cấu hình ở hai mode này không đổi (0 nhầm, 0 bỏ cuộc).

File nguồn: `results/w6/offline/evaluation.json` (cả chia dev/test theo task, danh sách ca nhầm `wrong`).

### Cách đọc
- **Cấu hình C** đúng cả 1.716/1.716, không nhầm, không bỏ cuộc. Chênh lệch so với A và B tập trung ở 12 lượt `W5_COMBINED` và `W5_ID` có hai ứng viên điểm gần bằng nhau (dòng lặp); A đoán nhầm 4 lượt, B bỏ cuộc 12 lượt, C giải được nhờ thứ tự dòng.
- **Cấu hình D** (thêm embedding hash) **kém hơn C**: 2 nhầm và 9 bỏ cuộc. Với encoder hash, embedding không bổ sung tín hiệu hữu ích ở đây, phù hợp với phân tích W4. Chưa thử sbert ở W6.
- 4 trong 6 mode (`CLASS`, `ORDER`, `STRUCTURE`, `TEXT`) gần như không cần thứ tự dòng: features đã đủ.

## Bổ sung: đo trên biến đổi mô phỏng (tie-break thứ tự dòng)
`healing/eval_order.py`: 61 trang M0 duy nhất, mỗi control thao tác được là một phần tử đích, 5 kiểu biến đổi × 3 seed (1.686 lượt mỗi ô). Kết quả tại `results/w6/offline/order_tiebreak/evaluation.json`.

| Kiểu | A đúng/nhầm/bỏ | B | C |
|---|---|---|---|
| `ids` | 1685 / 1 / 0 | 1680 / 0 / 6 | 1686 / 0 / 0 |
| `wrap` | 1683 / 3 / 0 | 1668 / 0 / 18 | 1686 / 0 / 0 |
| `combined` | 1668 / 18 / 0 | 1652 / 5 / 29 | 1678 / 5 / 3 |
| `decoy` | 1686 / 0 / 0 | 1680 / 0 / 6 | 1680 / 0 / 6 |

Trong `decoy`, số nút đổi nên `ord_n` lệch, C **từ chối đúng thiết kế**. Với `combined`, 5 ca nhầm còn lại có margin 0,035, không phải do hòa: khi `id`/`name` bị đổi thành chuỗi ngẫu nhiên, độ giống giữa hai chuỗi ngẫu nhiên là nhiễu đủ lớn để đảo thứ hạng. Hướng xử lý (chưa làm): bỏ qua `id`/`name` khi độ giống quá thấp.

## Giới hạn
- Đây là **độ chính xác chọn lại phần tử offline**, không phải task success hay recovery rate của agent. Chưa có runner online, chưa có B0 trên 390 lượt, chưa kiểm `wrong_target` (selector tìm thấy nhưng sai phần tử, như trục `order`).
- **Trần:** mỗi mode W5 chỉ đổi một khía cạnh (trừ `COMBINED`), nên features dễ đạt 100%. Kết quả C 1.716/1.716 không chứng minh tổng quát hóa sang mutation mới.
- **Seed:** `W5_ORDER` (83%) và `W5_STRUCTURE` (50%) trùng biến thể giữa hai seed, nên số lượt của hai mode này bị đếm trùng; dùng cột biến thể duy nhất khi báo cáo.
- Số mẫu độc lập nhỏ: nhiều task cùng mẫu form; các ca cần thứ tự dòng chỉ ở một vài trang (T004, T024).
- Ngưỡng và α chưa tinh chỉnh; mô phỏng không thêm hoặc bớt dòng thật, nên chưa kiểm clone/remove dòng đơn hàng (thiết kế sẽ từ chối khi `ord_n` đổi).
- Held-out W11 chưa truy cập.
- Phần viết mã và phân tích có AI hỗ trợ; người nộp chịu trách nhiệm kiểm lại.

## Tái lập
```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_healing.py        # kỳ vọng: 13 passed
.\.venv\Scripts\python.exe -m healing.eval_order --dataset runs/w4-trung-full --out results/w6/offline/order_tiebreak/evaluation.json
.\.venv\Scripts\python.exe -m healing.evaluate --dataset runs/w5-reproduction --encoder hash --out results/w6/offline/evaluation.json
```
Yêu cầu: `numpy`; không cần sentence-transformers.

## Việc tiếp theo (W7)
1. Chạy B0 trên 390 lượt để có mốc đối chứng và tỷ lệ B0 hỏng theo mode.
2. Chọn `min_margin` và α chỉ trên dev; bảng độ nhạy ngưỡng.
3. `check_found()` cho `wrong_target`; xử lý nhiễu `id`/`name`; thử sbert.
4. Đổi seed hoặc công thức xoay của `ORDER` và `STRUCTURE` (ra phiên bản 0.5.1).
