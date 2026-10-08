import sqlite3
from contextlib import contextmanager
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "minibiz.sqlite3"


@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    # Bật kiểm tra quan hệ khách hàng, đơn hàng và sản phẩm trên mỗi kết nối.
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL
            )
        """)
        # Giá sản phẩm là số nguyên VND, tránh sai số số thực.
        db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price INTEGER NOT NULL CHECK (price >= 0)
            )
        """)
        # ID nội bộ dùng để sinh mã ORD; đơn mới luôn bắt đầu ở pending.
        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','confirmed','shipped','delivered','cancelled')),
                created_at TEXT NOT NULL
            )
        """)
        # Mỗi SKU xuất hiện một lần trong một đơn; số lượng phải dương.
        db.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                order_id INTEGER NOT NULL REFERENCES orders(id),
                sku TEXT NOT NULL REFERENCES products(sku),
                qty INTEGER NOT NULL CHECK (qty > 0),
                PRIMARY KEY (order_id, sku)
            )
        """)
