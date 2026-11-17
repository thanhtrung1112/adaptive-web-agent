# Sửa tự nạp .env — v1.1

- Client đọc `.env` cố định tại gốc repo, không tìm lên thư mục cha; nhận UTF-8 có BOM, không nội suy biến, không ghi khóa ra log.
- Biến môi trường hiện có được ưu tiên hơn file, kể cả khi rỗng.
- Dependency mới: `python-dotenv==1.2.4` trong `requirements-w7.txt`.
- Kiểm thử: `python -m pytest -q tests/test_w7_client.py` — 19 passed in 4.02s; gồm SDK qua HTTP giả lập và test vị trí file/BOM/ưu tiên môi trường.
- Kiểm kết nối thật: `python -m llm.smoke --live --output runs/w7-api-smoke-dotenv-v1` — `API smoke: passed`, tối đa một request và 64 output token.
- `smoke/result.json` và `smoke/calls.jsonl` được sao từ lượt thật. Không chứa file `.env` hoặc khóa API.

Không sửa checksum hoặc nguồn của bằng chứng B0/A1 v1. Chưa có kết quả benchmark A2 hoặc điểm chất lượng LLM; smoke chỉ chứng minh kết nối và hợp đồng Structured Outputs hoạt động.
