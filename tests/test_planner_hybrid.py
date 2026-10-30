"""Workflow safety and real M0 feasibility. Fixtures do not measure LLM extraction."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from planner.core import make_request
from planner.intent import validate
from planner.workflows import compile_intent, validate_workflow


def operation(kind, values=None, items=None):
    return {'kind':kind,'slots':[{'key':k,'value':v,'source':v} for k,v in (values or {}).items()],
            'items':items or []}


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.request=make_request('Đổi số cho hoa@example.com thành 0909998888',max_steps=30)
        self.intent={'operations':[operation('update_phone',{'customer_email':'hoa@example.com','phone':'0909998888'})]}

    def test_missing_collects_all_fields_and_no_partial_actions(self):
        out=compile_intent({'operations':[operation('update_phone')]},make_request('Đổi số điện thoại'))
        self.assertEqual(out['plan']['status'],'needs_clarification')
        self.assertEqual(len(out['plan']['questions']),2)
        self.assertEqual(out['plan']['steps'],[])
        partial=compile_intent({'operations':[operation('find_customer',{'customer_email':'hoa@example.com'}),
                                               operation('update_phone')]},self.request)
        self.assertEqual(partial['plan']['steps'],[])

    def test_missing_edit_and_premature_save_are_rejected(self):
        out=compile_intent(self.intent,self.request)
        edit=next(i for i,m in enumerate(out['workflow']['steps']) if m['control']=='customer_edit')
        del out['plan']['steps'][edit];del out['workflow']['steps'][edit]
        with self.assertRaisesRegex(ValueError,'unavailable'): validate_workflow(out['plan'],out['workflow'],self.request)
        out=compile_intent(self.intent,self.request)
        fill=next(i for i,m in enumerate(out['workflow']['steps']) if m['control']=='edit_phone')
        del out['plan']['steps'][fill];del out['workflow']['steps'][fill]
        with self.assertRaisesRegex(ValueError,'complete'): validate_workflow(out['plan'],out['workflow'],self.request)

    def test_hallucinated_and_changed_source_are_rejected(self):
        bad=copy.deepcopy(self.intent);bad['operations'][0]['slots'][0]['value']='fake@example.com'
        with self.assertRaisesRegex(ValueError,'invented'): validate(bad,self.request['goal'])
        bad=copy.deepcopy(self.intent);bad['operations'][0]['slots'][0]['source']='Not in goal'
        with self.assertRaisesRegex(ValueError,'span'): validate(bad,self.request['goal'])

    def test_sku_source_cannot_borrow_quantity_from_another_item(self):
        goal='Tạo đơn hoa@example.com: SKU-100 số lượng 2, SKU-205 số lượng 3'
        item={'sku':'SKU-100','quantity':3,'source':'SKU-100 số lượng 2'}
        bad={'operations':[operation('create_order',{'customer_email':'hoa@example.com'},[item])]}
        with self.assertRaisesRegex(ValueError,'Quantity'): validate(bad,goal)

    def test_two_product_lines_no_extra_initial_row_and_exact_values(self):
        request=make_request('Tạo đơn hoa@example.com: SKU-100 số lượng 2, SKU-205 số lượng 3',max_steps=30)
        items=[{'sku':'SKU-100','quantity':2,'source':'SKU-100 số lượng 2'},
               {'sku':'SKU-205','quantity':3,'source':'SKU-205 số lượng 3'}]
        out=compile_intent({'operations':[operation('create_order',{'customer_email':'hoa@example.com'},items)]},request)
        self.assertEqual(sum(m['control']=='add_line' for m in out['workflow']['steps']),1)
        self.assertEqual([s['value'] for s,m in zip(out['plan']['steps'],out['workflow']['steps']) if m['control']=='line_qty'],['2','3'])
        # An extra blank row blocks submit even though its JSON remains valid.
        idx=len(out['plan']['steps'])-1
        out['plan']['steps'].insert(idx,{'action':'click','target':'Nút Thêm dòng sản phẩm','value':'','url':'','expected':''})
        out['workflow']['steps'].insert(idx,{'control':'add_line','argument':'','row':0})
        with self.assertRaisesRegex(ValueError,'blank'): validate_workflow(out['plan'],out['workflow'],request)

    def test_forward_reference_and_unsupported_never_execute(self):
        request=make_request('Tạo ticket tiêu đề Help cho đơn vừa tạo')
        op=operation('create_ticket',{'subject':'Help'})
        op['slots'].append({'key':'order_id','value':'$last_order','source':'đơn vừa tạo'})
        out=compile_intent({'operations':[op]},request)
        self.assertEqual(out['plan']['status'],'needs_clarification')
        self.assertFalse(out['plan']['steps'])
        out=compile_intent({'operations':[operation('unsupported')]},make_request('Xóa khách'))
        self.assertEqual(out['plan']['status'],'unsupported')
        self.assertFalse(out['plan']['steps'])

    def test_budget_and_control_value_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError,'max_steps'): compile_intent(self.intent,make_request(self.request['goal'],max_steps=2))
        out=compile_intent(self.intent,self.request)
        out['plan']['steps'][1]['value']='other@example.com'
        with self.assertRaises(ValueError): validate_workflow(out['plan'],out['workflow'],self.request)

    def test_plan_and_metadata_cannot_change_the_intent_together(self):
        request=make_request(self.request['goal']+'; email đối chiếu other@example.com',max_steps=30)
        out=compile_intent(self.intent,request)
        out['plan']['steps'][1]['value']='other@example.com'
        out['workflow']['steps'][1]['argument']='other@example.com'
        out['plan']['steps'][1]['target']='Ô tìm khách hàng theo email'
        with self.assertRaisesRegex(ValueError,'intent'):
            validate_workflow(out['plan'],out['workflow'],request,self.intent)

    def test_invalid_llm_output_is_not_replaced_with_a_scripted_intent(self):
        from planner.hybrid import run
        with tempfile.TemporaryDirectory() as temp, patch('planner.hybrid.generate',return_value={
                'done':True,'message':{'content':'not json'}}):
            result=run(self.request,'fixture','http://127.0.0.1:11434',Path(temp)/'output')
            self.assertFalse(result['schema_valid'])
            self.assertNotIn('plan',result)
            self.assertEqual(len(result['attempts']),2)
            self.assertIsNone(result['task_success'])

    def test_valid_llm_intent_compiles_and_retains_provenance(self):
        from planner.hybrid import run
        raw={'done':True,'message':{'content':json.dumps(self.intent)}}
        with tempfile.TemporaryDirectory() as temp, patch('planner.hybrid.generate',return_value=raw) as model:
            with patch('planner.hybrid.httpx.Client') as client:
                client.return_value.__enter__.return_value.get.return_value.json.return_value={'models':[]}
                result=run(self.request,'fixture','http://127.0.0.1:11434',Path(temp)/'output')
            self.assertTrue(result['schema_valid'])
            self.assertEqual(result['intent'],self.intent)
            self.assertIn('customer_edit',[m['control'] for m in result['workflow']['steps']])
            self.assertIs(model.call_args.kwargs['think'],False)
            self.assertIn('operations',model.call_args.kwargs['schema']['properties'])
            self.assertEqual(result['attempts'][0]['raw_response'],raw)


class M0FeasibilityTests(unittest.TestCase):
    # Execute generated workflow controls on an isolated real browser/server, without an LLM fixture claim.
    def test_customer_order_support_and_runtime_chain(self):
        from planner.verify_m0 import isolated_m0, execute
        from playwright.sync_api import sync_playwright
        from app.seed import reset_database
        goal=('Tạo An email an.plan@example.com phone 0901231234; tạo đơn khách này '
              'SKU-100 số lượng 2; ticket Cần hỗ trợ cho đơn vừa tạo')
        chain={'operations':[operation('create_customer',{'name':'An','customer_email':'an.plan@example.com','phone':'0901231234'}),
                             operation('create_order',{},[{'sku':'SKU-100','quantity':2,'source':'SKU-100 số lượng 2'}]),
                             operation('create_ticket',{'subject':'Cần hỗ trợ'})]}
        chain['operations'][1]['slots']=[{'key':'customer_email','value':'$last_customer','source':'khách này'}]
        chain['operations'][2]['slots'].append({'key':'order_id','value':'$last_order','source':'đơn vừa tạo'})
        scenarios=[(goal,chain),
                   ('Đổi tran.hoa@example.com thành 0909998888',{'operations':[operation('update_phone',{'customer_email':'tran.hoa@example.com','phone':'0909998888'})]}),
                   ('Đóng TCK-2002 ghi chú Đã giải quyết',{'operations':[operation('close_ticket',{'ticket_id':'TCK-2002','note':'Đã giải quyết'})]})]
        with isolated_m0() as base, sync_playwright() as pw:
            browser=pw.chromium.launch()
            try:
                for goal,intent in scenarios:
                    with self.subTest(goal=goal):
                        reset_database();request=make_request(goal,max_steps=30)
                        compiled=compile_intent(intent,request)
                        bundle={**compiled,'intent':intent,'request':request}
                        with browser.new_context() as ctx:
                            result=execute(ctx.new_page(),base,bundle)
                            self.assertTrue(result['persisted_state_matches_intent'],result)
                            if intent is chain: self.assertRegex(result['bindings']['$last_order'],r'^ORD-\d+$')
            finally: browser.close()
