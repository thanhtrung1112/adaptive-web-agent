"""W5 acceptance: real five-axis transformations and unchanged business semantics."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from playwright.sync_api import sync_playwright
from app.mutations import Tree, opaque_id
from app.mutations_w5 import MODES, mutate, nodes
from dom_snapshot.run import isolated_app

ROOT=Path(__file__).resolve().parents[1]
SOURCE='''<html><head></head><body><nav><a href="/customers">Khách hàng</a><a href="/orders">Đơn hàng</a></nav>
<form action="/customers/new" method="post"><label for="email">Email</label><input id="email" class="container" data-test="field" name="email"><button>Lưu</button></form>
<table><thead><tr><th>A</th><th>B</th><th>C</th></tr></thead><tbody><tr><td>a</td><td>b</td><td>c</td></tr><tr><td colspan="3">Empty</td></tr></tbody></table></body></html>'''


class MutationW5Tests(unittest.TestCase):
    def test_axes_are_real_and_separate(self):
        base=Tree(SOURCE).root
        for mode in MODES:
            with self.subTest(mode=mode):
                result=mutate(SOURCE,mode,17)
                self.assertNotEqual(result,SOURCE)
                tree=Tree(result).root
                ns=list(nodes(tree)); inp=next(n for n in ns if n.tag=='input')
                self.assertEqual(inp.attrs['name'],'email')
                if mode in ('W5_ID','W5_COMBINED'):
                    self.assertEqual(inp.attrs['id'],opaque_id('email',17))
                    self.assertEqual(next(n for n in ns if n.tag=='label').attrs['for'],inp.attrs['id'])
                else: self.assertEqual(inp.attrs['id'],'email')
                if mode in ('W5_CLASS','W5_COMBINED'):
                    self.assertNotEqual(inp.attrs['class'],'container')
                    self.assertNotIn('data-test',inp.attrs)
                    self.assertIn('.'+opaque_id('container',17),result)
                else: self.assertEqual(inp.attrs['class'],'container')
                if mode in ('W5_TEXT','W5_COMBINED'): self.assertNotIn('>Email</label>',result)
                if mode in ('W5_ORDER','W5_COMBINED'):
                    self.assertIn('<th>B</th><th>C</th><th>A</th>',result) if 17%2==0 else self.assertIn('<th>C</th><th>A</th><th>B</th>',result)
                    self.assertIn('<td colspan="3">Empty</td>',result)
                if mode in ('W5_STRUCTURE','W5_COMBINED'): self.assertIn('display:contents',result)

    def test_cross_process_reproducibility_and_seed_variation(self):
        for mode in MODES:
            a=mutate(SOURCE,mode,17)
            code=f'from app.mutations_w5 import mutate; import hashlib; print(hashlib.sha256(mutate({SOURCE!r},{mode!r},17).encode()).hexdigest())'
            self.assertEqual(hashlib.sha256(a.encode()).hexdigest(),subprocess.check_output([sys.executable,'-c',code],cwd=ROOT,text=True).strip())
            self.assertNotEqual(a,mutate(SOURCE,mode,18))

    def test_invalid_mode_and_seed(self):
        for mode,seed in [('M5',17),('W5_ID',True),('W5_ID',-1),('W5_ID',2147483648)]:
            with self.assertRaises(ValueError): mutate(SOURCE,mode,seed)

    def test_runtime_column_alignment_classes_labels_dynamic_rows(self):
        with tempfile.TemporaryDirectory() as tmp, isolated_app(Path(tmp)) as base, sync_playwright() as pw:
            browser=pw.chromium.launch()
            try:
                widths=[]
                for mode in ('M0',*MODES):
                    for seed in (17,18):
                        with self.subTest(mode=mode,seed=seed), browser.new_context() as ctx:
                            page=ctx.new_page(); page.set_default_timeout(3000)
                            page.goto(f'{base}/customers?mutation={mode}&seed={seed}')
                            original=page.content(); page.reload(); self.assertEqual(page.content(),original)
                            widths.append(page.locator('main').evaluate('el=>Math.round(el.getBoundingClientRect().width)'))
                            headers=page.locator('th').all_text_contents()
                            cells=page.locator('tbody tr').first.locator('td').all_text_contents()
                            self.assertIn('@',cells[headers.index('Email')])
                            if mode in ('W5_ORDER','W5_COMBINED'): self.assertNotEqual(headers[0],'ID')
                            page.goto(f'{base}/orders/new')
                            def field(name): return page.locator('#'+(opaque_id(name,seed) if mode in ('W5_ID','W5_COMBINED') else name))
                            field('add-order-line').click(); field('add-order-line').click()
                            page.locator('fieldset').first.locator('button').click()
                            field('order-sku-2').select_option('SKU-205'); field('order-qty-2').fill('3')
                            self.assertTrue(field('order-qty-2').evaluate('el=>el.labels.length===1'))
                            ids=page.locator('[id]').evaluate_all('els=>els.map(el=>el.id)')
                            self.assertEqual(len(ids),len(set(ids)))
                self.assertEqual(len(set(widths)),1)
            finally: browser.close()


if __name__=='__main__': unittest.main()
