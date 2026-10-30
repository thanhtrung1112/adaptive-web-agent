# Bàn giao GitHub và nộp W5

## Hai Issue theo thành viên

Milestone: `Tuan5`, hạn 31/10/2026. Không đóng Issue hoặc tag trước peer review.

**Sv Vũ Văn Bình – Bộ mutation năm trục cho MiniBiz, benchmark 0.5.0**

Assignee đề xuất `hnib1908`; reviewer đề xuất `thanhtrung1112`.

- [x] Có ID/class/text/order/structure và tổ hợp trên app thật.
- [x] Context, IDREF, JS dòng Order và nghiệp vụ được kiểm thử.
- [x] 390/390 oracle replays, snapshot/checksum và dataset bàn giao.
- [ ] Bình nhận bàn giao, đọc lại code và xác nhận công việc.
- [ ] Trung review chéo và ghi kết quả thực tế.

**Sv Nguyễn Thành Trung – Version benchmark và kiểm chứng hiệu lực mutation W5**

Assignee đề xuất `thanhtrung1112`; reviewer đề xuất `hnib1908`.

- [x] Có manifest 0.5.0, task/data/source checksum và cách tái lập.
- [x] 65 probe; nhận diện missing/ambiguous/wrong target.
- [x] Có tests, báo cáo, metrics và bộ evidence.
- [ ] Trung nhận bàn giao, chạy lại và xác nhận.
- [ ] Bình review kết quả và ghi nhận.

Nội dung hai Issue cần ghi rõ sản phẩm được chuẩn bị với hỗ trợ Codex; checklist
trên mô tả trạng thái sản phẩm, không giả định thành viên đã review.

## PR

Title: `[W5] Bộ mutation năm trục và benchmark MiniBiz 0.5.0`

Nội dung đề xuất:

```markdown
## Vấn đề và thay đổi
Mutation W4 chỉ đổi ID, nhãn và wrapper. W5 thêm mode độc lập cho ID/class/text/
order/structure, mode tổ hợp và phiên bản benchmark 0.5.0. Reorder giữ khớp cột–cell;
đổi class có CSS tương đương; JS Order giữ label/ID sau clone/remove.

## Kiểm chứng
- 85/85 kiểm thử hồi quy.
- 390/390 oracle replays cho 30 task, M0 và sáu mode W5 với hai seed phát triển.
- 2.249 snapshot, 1.716 cặp được kiểm schema/hash/provenance.
- 65 frozen-locator probes; năm trục làm hỏng locator tương ứng.
- Evidence/W05 và docs/mutation-benchmark-v0.5.0.md.

## Giới hạn
Oracle không phải A1/A2 success. Probe không phải full B0 matrix.
Không có nghiệm thu peer review/GVHD hoặc xác nhận nộp LMS trong kết quả local.
```

Thêm `Closes #...` bằng số Issue thật sau khi tạo. Chọn reviewer khác tác giả,
milestone Tuan5. PR W3 #19 đang độc lập: tránh đưa thay đổi chưa merge đó vào PR W5.

## Các bước chốt tuần

1. Hai thành viên kiểm tra diff và evidence, xác nhận vai trò thực tế.
2. Reviewer chạy lại hoặc kiểm chứng log/checksum, ghi review trên PR.
3. Xử lý góp ý, merge PR W5 theo quy trình của nhóm.
4. Gắn tag `w05` trên commit đã review/tích hợp; cập nhật manifest với URL/commit thật.
5. Nộp báo cáo W5, bản quyển cập nhật Chương II và gói evidence trên LMS trước hạn.

Không tự điền điểm trong tệp XLSM gốc của GVHD.
