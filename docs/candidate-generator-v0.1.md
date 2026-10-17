# Candidate generator v0.1

## Mục đích
Khi locator cũ không còn khớp, generator nhận **mô tả phần tử gốc** (đặc trưng lấy từ DOM snapshot ở trạng thái M0) và danh sách control của trang mới, rồi trả về các ứng viên xếp theo độ giống, kèm điểm từng đặc trưng. Ranking bằng embedding (W4) và LLM fallback (W5-W6) sẽ nhận danh sách này.

## Đầu vào
Snapshot schema v0.1 (`docs/dom-snapshot-v0.1.md`, `results/w3/dom_samples_expanded_v0.1/`). Chỉ giữ control thao tác được: `a`, `button`, `input`, `select`, `textarea`, đang hiện, không bị vô hiệu, không phải `hidden`.

## Đặc trưng và trọng số
| Đặc trưng | Cách so | Trọng số |
|---|---|---|
| `tag`, `type`, `form` | giống hoặc khác | 3, 1, 1 |
| `text`, `label`, `placeholder`, `id`, `name`, `href` | độ giống chuỗi (`difflib`) | 3, 3, 1.5, 2, 2, 2 |
| `path` | tỉ lệ đoạn đường dẫn trùng từ gốc | 1 |
| `options` | tỉ lệ lựa chọn trùng | 1 |

Đặc trưng mà phần tử gốc không có thì bỏ qua. Trọng số là giá trị khởi đầu chọn tay, chưa được tối ưu.

## Ground truth
Lấy từ selector của baseline (`baseline/scripts.py`): `#id`, `a[href=...]`, `a[href^=...]` được tra trong từng trạng thái đã thu. Kết quả: **79 cặp (trạng thái, phần tử)**, không selector nào bị bỏ qua. Đây là các phần tử đại diện, không phải từng bước của 20 task.

## Đánh giá
`python -m candidates.evaluate` biến đổi snapshot (đổi `id`/`name`/`class`, đổi nhãn bằng từ đồng nghĩa, thêm lớp bọc, thêm nút mồi, và tổ hợp) rồi đo hạng của phần tử đúng. Kết quả ghi vào `results/w3/candidate_generator_v0.1/evaluation.json`.

| Kiểu đổi | top-1 | top-3 | MRR |
|---|---|---|---|
| không đổi / id / nhãn / lớp bọc / nút mồi | 1.000 | 1.000 | 1.000 |
| tổ hợp (id + nhãn + lớp bọc) | 0.975 | 1.000 | 0.987 |

## Phân tích lỗi
2 ca sai, đều ở trạng thái `orders-two-lines` (`#order-sku-1`, `#order-qty-2`): form có hai dòng sản phẩm giống hệt nhau, sau khi đổi `id` và nhãn chỉ còn vị trí để phân biệt, mà generator chưa có đặc trưng "thứ tự trong nhóm các control cùng loại". Đề xuất cho W4: thêm đặc trưng này.

## Giới hạn
- Biến đổi chỉ làm trên snapshot, **chưa phải mutation thật** của app; mỗi lần chỉ đổi một khía cạnh nên kết quả gần 100% là dễ đoán.
- Mỗi trang chỉ có khoảng 11 control, nên bài toán còn nhỏ; layout (M4) chưa được thử.
- Từ đồng nghĩa trong `mutate.py` do nhóm tự chọn, có thể thiên lệch.
- Chưa dùng embedding, nên các nhãn khác hẳn về chữ nhưng cùng nghĩa chỉ được cứu bởi các đặc trưng khác.
