"""Kiểm tra DOM thật: nhãn, trạng thái runtime, cấu trúc và schema lỗi."""
import copy
import unittest
from jsonschema import ValidationError
from playwright.sync_api import sync_playwright
from dom_snapshot.capture import capture
from dom_snapshot.parser import validate_snapshot


class DOMSnapshotTests(unittest.TestCase):
    # Dùng browser thật để không suy đoán visibility từ HTML.
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':1280,'height':800})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()

    def snapshot(self):
        return capture(self.page, 'fixture', 'test', 'fixture', {})[1]

    def test_labels_runtime_values_and_disabled_ancestor(self):
        self.page.set_content('<label for="email">Email khách hàng</label><input id="email">'
            '<fieldset disabled><input id="disabled"></fieldset>'
            '<div style="display:none"><button id="hidden">Ẩn</button></div>'
            '<input id="ro" readonly><label>Tên <input id="wrapped"></label>')
        self.page.locator('#email').fill('sample@example.com')
        rows = {e['attributes'].get('id'):e for e in self.snapshot()['elements']}
        self.assertEqual(rows['email']['label'], 'Email khách hàng')
        self.assertEqual(rows['email']['value'], 'sample@example.com')
        self.assertFalse(rows['disabled']['enabled'])
        self.assertFalse(rows['hidden']['visible'])
        self.assertTrue(rows['ro']['readonly'])
        self.assertEqual(rows['wrapped']['label'], 'Tên')

    def test_dynamic_nodes_and_unique_references(self):
        self.page.set_content('<div><button>A</button><button>B</button></div>')
        before = self.snapshot()
        self.page.evaluate("document.querySelector('div').appendChild(document.createElement('input'))")
        after = self.snapshot()
        self.assertEqual(len(after['elements']), len(before['elements'])+1)
        for e in after['elements']:
            loc = self.page.locator('xpath='+e['locator']['value'])
            self.assertEqual(loc.count(), 1)
            self.assertEqual(loc.evaluate('(e)=>e.localName'), e['tag'])

    def test_reject_duplicate_ids_broken_parent_and_wrong_type(self):
        self.page.set_content('<button>Save</button>')
        original = self.snapshot()
        invalid = copy.deepcopy(original)
        invalid['elements'][-1]['element_id'] = invalid['elements'][0]['element_id']
        with self.assertRaises(ValueError): validate_snapshot(invalid)
        invalid = copy.deepcopy(original)
        invalid['elements'][-1]['parent_id'] = 'e9999'
        with self.assertRaises(ValueError): validate_snapshot(invalid)
        invalid = copy.deepcopy(original)
        invalid['elements'][-1]['visible'] = 'true'
        with self.assertRaises(ValidationError): validate_snapshot(invalid)

    def test_labelledby_and_capture_does_not_mutate_dom(self):
        self.page.set_content('<span id="a">Gửi</span><span id="b">ticket</span>'
            '<button aria-labelledby="a b" aria-label="Fallback">OK</button>')
        original = self.page.content()
        button = next(e for e in self.snapshot()['elements'] if e['tag']=='button')
        self.assertEqual(button['name_hint'], 'Gửi ticket')
        self.assertEqual(self.page.content(), original)

    # Select/textarea phải phản ánh giá trị runtime, không lấy thuộc tính HTML cũ.
    def test_selected_options_and_textarea_runtime(self):
        self.page.set_content('<label for="s">Trạng thái</label><select id="s">'
                              '<option value="open" selected>Mở</option>'
                              '<option value="closed">Đóng</option></select>'
                              '<label for="note">Ghi chú</label><textarea id="note">Cũ</textarea>')
        self.page.locator('#s').select_option('closed')
        self.page.locator('#note').fill('Đã hoàn tiền')
        elements = self.snapshot()['elements']
        by_id = {e['attributes'].get('id'):e for e in elements}
        self.assertEqual(by_id['s']['value'], 'closed')
        self.assertEqual(by_id['s']['label'], 'Trạng thái')
        self.assertEqual(by_id['note']['value'], 'Đã hoàn tiền')
        options = {e['value']:e['selected'] for e in elements if e['tag']=='option'}
        self.assertEqual(options, {'open':False, 'closed':True})


if __name__ == '__main__':
    unittest.main()
