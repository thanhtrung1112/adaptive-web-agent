"""Kiểm tra checksum: python scripts/seed_manifest.py; cập nhật: thêm --update."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed_v1.json"
MANIFEST = ROOT / "data" / "manifest.json"


# Update chủ động chuẩn hóa LF; chế độ mặc định chỉ kiểm tra, không sửa tệp.
def main():
    parser = argparse.ArgumentParser(description="Kiểm tra SHA-256 của seed theo byte thực tế.")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    raw = SEED.read_bytes()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.update:
        raw = raw.replace(b"\r\n", b"\n")
        SEED.write_bytes(raw)
        manifest["sha256"] = hashlib.sha256(raw).hexdigest()
        MANIFEST.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    if b"\r" in raw or manifest.get("path") != "data/seed_v1.json" or digest != manifest.get("sha256"):
        print("FAIL: seed phải dùng LF và SHA-256 phải khớp manifest. Chạy lại với --update nếu thay đổi seed có chủ đích.")
        return 1
    print(f"OK: seed LF, SHA-256 = {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
