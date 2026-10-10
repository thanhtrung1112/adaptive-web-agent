import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.seed import reset_database
from baseline.checker import check_all
from baseline.scripts import SCRIPTS

ROOT = Path(__file__).resolve().parents[1]


# Các mục tiêu phải chưa đạt trên seed; tránh baseline thành công mà không thao tác.
class CheckerTests(unittest.TestCase):
    def test_all_twenty_tasks_require_action(self):
        with tempfile.TemporaryDirectory() as temp, patch('app.db.DB_PATH', Path(temp)/'test.sqlite3'):
            reset_database()
            with TestClient(app) as client:
                tasks = json.loads((ROOT/'tasks/tasks_w2.json').read_text(encoding='utf-8'))
                for task in tasks:
                    with self.subTest(task=task['id']):
                        self.assertFalse(check_all(lambda p: client.get(p).json(), task)[0])
                        self.assertLessEqual(len(SCRIPTS[task['id']]), task['max_steps'])

    # CSV lặp dòng hoặc thiếu header phải bị đánh trượt, kể cả API trả tập rỗng.
    def test_csv_rejects_duplicates_and_missing_header(self):
        task = {'success_criteria':[{'type':'download_check','expect':{'order_ids_equal_to_api':'/api/orders'}}]}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'orders.csv'
            path.write_text('id\nORD-1001\nORD-1001\n',encoding='utf-8')
            self.assertFalse(check_all(lambda p:{'orders':[{'id':'ORD-1001'}]},task,path)[0])
            path.write_text('',encoding='utf-8')
            self.assertFalse(check_all(lambda p:{'orders':[]},task,path)[0])

    # Ticket gắn sai đơn phải thất bại dù tiêu đề và khách hàng đúng.
    def test_chain_wrong_order_fails(self):
        task={'success_criteria':[{'type':'api_check','endpoint':'/api/tickets?customer_email=a@example.com',
              'expect':{'count':1,'linked_to_new_order':True}}]}
        def get(path):
            if path.startswith('/api/tickets'): return {'count':1,'tickets':[{'order_id':'ORD-1001'}]}
            return {'orders':[{'id':'ORD-1002'}]}
        self.assertFalse(check_all(get,task)[0])

    # Giữ nguyên 10 task W1 khi mở rộng tập W2.
    def test_pilot_preserved(self):
        pilot=json.loads((ROOT/'tasks/pilot_tasks.json').read_text(encoding='utf-8'))
        w2=json.loads((ROOT/'tasks/tasks_w2.json').read_text(encoding='utf-8'))
        self.assertEqual(w2[:10],pilot)
