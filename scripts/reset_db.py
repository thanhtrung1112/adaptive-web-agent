"""Chạy từ thư mục gốc: python scripts/reset_db.py --yes"""

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.db import DB_PATH
from app.seed import reset_database


# Reset chủ động cả CRM và Order; không chạy tự động khi mở ứng dụng.
def main():
    parser = argparse.ArgumentParser(description="Xóa dữ liệu CRM/Order/Support chạy thử và nạp seed_v1.")
    parser.add_argument("--yes", action="store_true", help="Đồng ý thay dữ liệu hiện tại bằng seed.")
    args = parser.parse_args()

    if not args.yes:
        parser.exit(
            message=f"Chưa thay đổi dữ liệu. Database: {DB_PATH}\n"
            "Dừng server rồi thêm --yes để reset dữ liệu CRM và Order.\n"
        )

    count = reset_database()
    print(f"Đã reset seed_v1 (CRM + Order + Support): {count} khách hàng, đã nạp sản phẩm, đơn mẫu, nhân viên và ticket.")
    print(f"Database: {DB_PATH}")


if __name__ == "__main__":
    main()
