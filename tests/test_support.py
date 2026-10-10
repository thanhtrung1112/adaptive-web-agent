import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.seed import reset_database


# Kiểm thử tích hợp trên database tạm; không tác động dữ liệu người dùng.
class SupportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        patcher = patch('app.db.DB_PATH', Path(temp.name) / 'test.sqlite3')
        patcher.start()
        self.addCleanup(patcher.stop)
        reset_database()
        self.client = self.enterContext(TestClient(app))

    # T007 tạo đúng một ticket open cho ORD-1002.
    def test_t007_create(self):
        for url in ['/tickets', '/tickets/new', '/tickets/TCK-2001']:
            self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post('/tickets/new', data={'order_id':'ORD-1002','subject':'Giao hàng chậm'})
        self.assertEqual(response.status_code, 200)
        result = self.client.get('/api/tickets?order_id=ORD-1002').json()
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['tickets'][0]['subject'], 'Giao hàng chậm')
        self.assertEqual(result['tickets'][0]['status'], 'open')

    # T008/T009 lưu cả trạng thái và dữ liệu liên quan; reset phục hồi seed.
    def test_t008_t009_and_reset(self):
        before = self.client.get('/api/tickets').json()
        self.assertEqual(self.client.post('/tickets/TCK-2001/assign', data={'assignee_id':'1'}).status_code, 200)
        assigned = self.client.get('/api/tickets/TCK-2001').json()
        self.assertEqual(assigned['assignee_name'], 'Hoàng Quang Huy')
        self.assertEqual(assigned['status'], 'in_progress')
        self.assertEqual(self.client.post('/tickets/TCK-2002/close', data={'note':'Đã hoàn tiền cho khách'}).status_code, 200)
        closed = self.client.get('/api/tickets/TCK-2002').json()
        self.assertEqual(closed['note'], 'Đã hoàn tiền cho khách')
        self.assertEqual(closed['status'], 'closed')
        reset_database()
        self.assertEqual(self.client.get('/api/tickets').json(), before)

    # T010 đối chiếu ID đơn mới thật, không dùng cờ thành công do ứng dụng tự trả.
    def test_t010_chain(self):
        self.assertIn('Võ Thanh Tâm', self.client.get('/customers?email=vo.tam@example.com').text)
        self.assertIn('/orders/new?customer_id=4', self.client.get('/customers/4').text)
        self.assertIn('value="4" selected', self.client.get('/orders/new?customer_id=4').text)
        created = self.client.post('/orders/new', data={'customer_id':'4','sku':'SKU-100','qty':'2'}, follow_redirects=False)
        order_id = created.headers['location'].split('/')[-1]
        self.assertIn('/tickets/new?order_id='+order_id, self.client.get(created.headers['location']).text)
        self.assertIn(f'value="{order_id}" selected', self.client.get('/tickets/new?order_id='+order_id).text)
        self.client.post('/tickets/new', data={'order_id':order_id,'subject':'Hỏi thời gian giao'})
        orders = self.client.get('/api/orders?customer_email=vo.tam@example.com').json()
        tickets = self.client.get('/api/tickets?customer_email=vo.tam@example.com').json()
        self.assertEqual(orders['count'], 1)
        self.assertEqual(tickets['count'], 1)
        self.assertEqual(orders['orders'][0]['items'], [{'sku':'SKU-100','qty':2}])
        self.assertEqual(tickets['tickets'][0]['order_id'], orders['orders'][0]['id'])
        self.assertEqual(tickets['tickets'][0]['subject'], 'Hỏi thời gian giao')

    # Lỗi đầu vào không tạo/sửa ticket, và không làm mất quan hệ hiện có.
    def test_invalid_input(self):
        before = self.client.get('/api/tickets').json()
        for payload in [{'order_id':'ORD-9999','subject':'Test'}, {'order_id':'ORD-1002','subject':'   '}]:
            self.assertEqual(self.client.post('/tickets/new', data=payload).status_code, 400)
        self.assertEqual(self.client.post('/tickets/TCK-2001/assign', data={'assignee_id':'999'}).status_code, 400)
        self.assertEqual(self.client.post('/tickets/TCK-2002/close', data={'note':' '}).status_code, 400)
        self.assertEqual(self.client.get('/tickets/TCK-9999').status_code, 404)
        self.assertEqual(self.client.get('/api/tickets').json(), before)


if __name__ == '__main__':
    unittest.main()
