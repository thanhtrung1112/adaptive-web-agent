"""W4 contract, genuine mutation, context persistence and dynamic form regression tests."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from playwright.sync_api import sync_playwright
from app.main import app
from app.mutations import MODES, mutate_html, opaque_id
from app.seed import reset_database
from baseline.checker import check_all
from baseline.run_baseline import SCRIPTS
from dom_snapshot.capture import capture, save_snapshot
from dom_snapshot.run import isolated_app
from w4.oracle import oracle_css
from w4.dataset import ranking_inputs
from w4.validate_dataset import validate

ROOT=Path(__file__).resolve().parents[1]


class W4ContractTests(unittest.TestCase):
    def test_thirty_tasks_preserve_w2_and_require_action(self):
        tasks=json.loads((ROOT/'tasks/tasks_w4.json').read_text(encoding='utf-8'))
        old=json.loads((ROOT/'tasks/tasks_w2.json').read_text(encoding='utf-8'))
        self.assertEqual(tasks[:20],old)
        self.assertEqual([t['id'] for t in tasks],[f'T{i:03d}' for i in range(1,31)])
        self.assertEqual(len({t['goal'] for t in tasks}),30)
        schema=json.loads((ROOT/'tasks/task_schema.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as temp, patch('app.db.DB_PATH',Path(temp)/'test.sqlite3'):
            reset_database()
            with TestClient(app) as client:
                for task in tasks:
                    with self.subTest(task=task['id']):
                        Draft202012Validator(schema).validate(task)
                        self.assertFalse(check_all(lambda p:client.get(p).json(),task)[0])
                        self.assertLessEqual(len(SCRIPTS[task['id']]),task['max_steps'])

    # Same source/seed across processes, and M0 remains byte-identical.
    def test_pure_mutation_reproducible_across_processes(self):
        source='<p><label for="x">Email</label><input id="x" name="email"><a href="/customers">Lưu</a></p>'
        self.assertEqual(mutate_html(source,'M0',7),source)
        for mode in MODES[1:]:
            actual=mutate_html(source,mode,7)
            self.assertNotEqual(actual,source)
            code=f'from app.mutations import mutate_html; import hashlib; print(hashlib.sha256(mutate_html({source!r},{mode!r},7).encode()).hexdigest())'
            other=subprocess.check_output([sys.executable,'-c',code],cwd=ROOT,text=True).strip()
            self.assertEqual(hashlib.sha256(actual.encode()).hexdigest(),other)
            self.assertNotEqual(actual,mutate_html(source,mode,8))
            self.assertIn('name="email"',actual)
            self.assertNotIn('<div',actual)
            self.assertIn('action="/customers/new"',mutate_html('<form action="/customers/new" method="post"></form>',mode,7))

    def test_invalid_context_and_error_response_retain_mutation(self):
        with tempfile.TemporaryDirectory() as temp, patch('app.db.DB_PATH',Path(temp)/'test.sqlite3'):
            reset_database()
            with TestClient(app) as client:
                for query in ('mutation=M5','mutation=M1&seed=-1','mutation=M2&seed=bad','seed=2147483648'):
                    self.assertEqual(client.get('/customers?'+query).status_code,400)
                before=client.get('/api/customers').json()
                r=client.get('/customers/new?mutation=M1&seed=7')
                self.assertIn(opaque_id('customer-email',7),r.text)
                # Duplicate email renders HTTP 400; context persists even without query on POST.
                error=client.post('/customers/new',data={'name':'Duplicate','email':'tran.hoa@example.com','phone':'123'})
                self.assertEqual(error.status_code,400)
                self.assertIn(opaque_id('customer-email',7),error.text)
                self.assertEqual(client.get('/api/customers').json(),before)
                self.assertIn('swagger-ui',client.get('/docs').text)
                client.get('/customers?mutation=M0&seed=0')
                self.assertIn('id="customer-email"',client.get('/customers/new').text)


class W4BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='w4-browser-')
        cls.server=isolated_app(Path(cls.temp.name)); cls.base=cls.server.__enter__()
        cls.pw=sync_playwright().start(); cls.browser=cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.server.__exit__(None,None,None); cls.temp.cleanup()

    # Exercise add/remove/renumber on real mutated HTML, not an offline JSON edit.
    def test_dynamic_form_two_seeds_all_modes_and_labels(self):
        for mode in MODES:
            for seed in (7,8):
                with self.subTest(mode=mode,seed=seed):
                    reset_database()
                    with self.browser.new_context() as ctx:
                        page=ctx.new_page(); page.set_default_timeout(5000)
                        page.goto(f'{self.base}/orders/new?mutation={mode}&seed={seed}')
                        def loc(css): return page.locator(oracle_css(css,mode,seed))
                        loc('#order-customer').select_option(value='3')
                        loc('#add-order-line').click(); loc('#add-order-line').click()
                        page.locator('fieldset').first.locator('button').click()
                        self.assertEqual(page.locator('fieldset').count(),2)
                        loc('#order-sku-1').select_option(value='SKU-100'); loc('#order-qty-1').fill('2')
                        loc('#order-sku-2').select_option(value='SKU-205'); loc('#order-qty-2').fill('3')
                        self.assertTrue(loc('#order-sku-2').evaluate('el => el.labels.length === 1'))
                        ids=page.locator('[id]').evaluate_all('els => els.map(el => el.id)')
                        self.assertEqual(len(ids),len(set(ids)))
                        snap=capture(page,'dynamic','T004','dynamic',{})[1]
                        e=next(e for e in snap['elements'] if e['attributes'].get('id')==oracle_css('#order-qty-2',mode,seed)[1:])
                        self.assertEqual(e['value'],'3'); self.assertTrue(e['label'])
                        loc('#save-order').click(); page.wait_for_load_state('load')
                        data=ctx.request.get(self.base+'/api/orders?customer_email=pham.ha@example.com').json()
                        self.assertEqual(data['count'],1)
                        self.assertEqual({(i['sku'],i['qty']) for i in data['orders'][0]['items']},{('SKU-100',2),('SKU-205',3)})
                        self.assertEqual(next(c['value'] for c in ctx.cookies() if c['name']=='minibiz_mutation'),f'{mode}:{seed}')

    # Reloads are identical; real labels, GET search and links remain associated with context.
    def test_runtime_determinism_get_search_navigation_and_csv(self):
        for mode in MODES[1:]:
            with self.subTest(mode=mode), self.browser.new_context(accept_downloads=True) as ctx:
                reset_database(); page=ctx.new_page(); page.set_default_timeout(5000)
                page.goto(f'{self.base}/customers?mutation={mode}&seed=7')
                original=page.content(); page.reload(); self.assertEqual(page.content(),original)
                field=page.locator(oracle_css('#customer-search',mode,7))
                self.assertTrue(field.evaluate('el => el.labels.length === 1'))
                field.fill('pham.ha@example.com')
                page.locator(oracle_css('#search-customers',mode,7)).click()
                page.locator('table a').click()
                self.assertEqual(ctx.request.get(self.base+'/api/session/last_viewed_customer').json()['email'],'pham.ha@example.com')
                # Direct navigation without query uses the context cookie, including CSV download.
                page.goto(self.base+'/orders?from=2026-09-01&to=2026-09-15')
                with page.expect_download() as info: page.locator(oracle_css('#export-orders',mode,7)).click()
                self.assertIn('ORD-1003',Path(info.value.path()).read_text(encoding='utf-8-sig'))
                if mode=='M1': self.assertEqual(page.locator('#orders-from').count(),0)

    # The ranker sees only descriptor/candidates; schema/hash corruption must be rejected.
    def test_paired_dataset_contract_and_corrupt_html(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            ids={}
            for mode in ('M0','M3'):
                with self.browser.new_context() as ctx:
                    page=ctx.new_page(); page.goto(f'{self.base}/customers/new?mutation={mode}&seed=7')
                    html,snapshot=capture(page,mode,'T001','customers-new',{'mutation':mode,'mutation_seed':7,'data_seed':'seed_v1'})
                    ids[mode]=page.locator('#customer-name').evaluate("el => 'e'+(Array.from(document.querySelectorAll('*')).indexOf(el)+1)")
                    save_snapshot(root/'snapshots'/mode,html,snapshot)
                    self.assertNotIn(b'\r', (root/'snapshots'/mode/'features.json').read_bytes())
            pair={'task_id':'T001','step_index':2,'mutation':'M3','mutation_seed':7,
                  'reference_snapshot':'snapshots/M0/features.json','reference_element_id':ids['M0'],
                  'candidate_snapshot':'snapshots/M3/features.json','target_element_id':ids['M3']}
            (root/'ground_truth').mkdir()
            (root/'ground_truth/pairs.json').write_text(json.dumps([pair]),encoding='utf-8')
            result=validate(root); self.assertEqual(result['snapshot_count'],2)
            descriptor,candidates=ranking_inputs(root,pair)
            self.assertNotIn('target_element_id',descriptor)
            self.assertTrue(all('target_element_id' not in c and 'goal' not in c for c in candidates))
            from w4.dataset import read_snapshot
            with self.assertRaises(ValueError): read_snapshot(root,'../outside.json')
            (root/'snapshots/M3/dom.html').write_text('tampered',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'checksum'): validate(root)


if __name__=='__main__': unittest.main()
