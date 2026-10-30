"""Contract/transport tests; mocked responses are not LLM quality evidence."""
import copy
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import httpx
from jsonschema import ValidationError
from planner.core import make_request, messages, validate_plan
from planner.run import generate, run


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.request=make_request('Tìm khách hàng hoa@example.com')
        self.plan={'version':'0.2','status':'ready','objective':'Tìm khách hàng',
                   'entities':[],'questions':[], 'verification':[{'target':'khách','expected':'Đúng email'}], 'steps':[
                       {'action':'fill','target':'Ô tìm khách hàng theo email','value':'hoa@example.com','url':'','expected':''},
                       {'action':'verify','target':'','value':'','url':'','expected':'Hiển thị đúng email'}]}

    def test_ready_and_clarification_contract(self):
        validate_plan(self.plan,self.request)
        self.plan.update(status='needs_clarification',questions=['Email nào?'],steps=[],verification=[])
        validate_plan(self.plan,self.request)

    def test_reject_external_routes_and_bad_budget(self):
        for url in ('https://evil.test','//evil.test','/api/customers','/customers/1','/customers?x=1'):
            with self.subTest(url=url), self.assertRaises(ValueError): make_request('goal',url)
        with self.assertRaises(ValueError): make_request('goal',max_steps=True)

    def test_reject_invalid_action_values_and_selector(self):
        for field,value in (('target','#customer-email'),('value',''),('url','/orders')):
            plan=copy.deepcopy(self.plan);plan['steps'][0][field]=value
            with self.subTest(field=field), self.assertRaises((ValueError, ValidationError)): validate_plan(plan,self.request)

    def test_requires_verify_and_respects_step_budget(self):
        with self.assertRaises(ValueError): validate_plan(self.plan,make_request('goal',max_steps=1))
        self.plan['verification']=[]
        with self.assertRaises(ValueError): validate_plan(self.plan,self.request)

    def test_reject_invented_identifiers(self):
        self.plan['entities']=[{'name':'phone','value':'0987654321'}]
        with self.assertRaisesRegex(ValueError,'Invented'): validate_plan(self.plan,self.request)
        self.plan.update(status='needs_clarification',questions=['Số mới?'],steps=[],verification=[])
        with self.assertRaisesRegex(ValueError,'Invented'): validate_plan(self.plan,self.request)

    def test_clarification_cannot_execute(self):
        self.plan['status']='needs_clarification'
        with self.assertRaises(ValueError): validate_plan(self.plan,self.request)

    def test_transport_sends_schema_not_answers(self):
        def handler(request):
            payload=json.loads(request.content)
            self.assertFalse(payload['stream'])
            self.assertEqual(payload['format']['properties']['version']['const'],'0.2')
            self.assertNotIn('success_criteria',payload['messages'][1]['content'])
            return httpx.Response(200,json={'message':{'content':json.dumps(self.plan)},'done':True})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            response=generate(self.request,'test-model','http://127.0.0.1:11434',client)
            self.assertTrue(response['done'])
            with self.assertRaises(ValueError): generate(self.request,'test','http://external.test',client)
        self.assertEqual(set(json.loads(messages(self.request)[1]['content'])),{'goal','start_url','max_steps'})

    def test_thinking_false_is_explicit_and_default_omitted(self):
        payloads=[]
        def handler(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200,json={'done':True})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            generate(self.request,'fixture','http://localhost:11434',client)
            generate(self.request,'fixture','http://localhost:11434',client,think=False)
        self.assertNotIn('think',payloads[0])
        self.assertIs(payloads[1]['think'],False)


class PlannerLoggingTests(unittest.TestCase):
    # An interrupted evaluation must retain completed cases without claiming completion.
    def test_evaluation_preserves_progress_on_interruption(self):
        from planner.evaluate import main
        result={'schema_valid':True,'plan':{'status':'ready'},'latency_seconds':1.0}
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'evaluation'
            args=['evaluate','--model','fixture','--output',str(output),
                  '--cases','crm-paraphrase','order']
            with patch('sys.argv',args), patch('planner.evaluate.run',side_effect=[result,KeyboardInterrupt()]):
                with self.assertRaises(KeyboardInterrupt): main()
            progress=json.loads((output/'progress.json').read_text(encoding='utf-8'))
            self.assertFalse(progress['complete'])
            self.assertEqual(progress['completed_cases'],['crm-paraphrase'])
            self.assertEqual(len(json.loads((output/'summary.json').read_text(encoding='utf-8'))),1)

    def test_invalid_json_is_logged_without_success(self):
        with tempfile.TemporaryDirectory() as temp, patch('planner.run.generate', return_value={
            'done':True, 'message':{'content':'not json'}, 'eval_count':5}):
            result=run(make_request('Tìm khách'), 'fixture', 'http://127.0.0.1:11434', Path(temp)/'run')
            self.assertFalse(result['schema_valid'])
            self.assertIsNone(result['task_success'])
            self.assertIn('error',result)
            self.assertEqual(len(result['attempts']),2)
            saved=json.loads((Path(temp)/'run/trace.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['raw_response']['message']['content'],'not json')


    def test_single_repair_returns_model_plan_and_accumulates_usage(self):
        good={'version':'0.2','status':'unsupported','objective':'Không hỗ trợ xóa',
              'entities':[],'questions':[],'steps':[],'verification':[]}
        responses=[{'done':True,'message':{'content':'bad'},'prompt_eval_count':10,'eval_count':2},
                   {'done':True,'message':{'content':json.dumps(good)},'prompt_eval_count':20,'eval_count':8}]
        with tempfile.TemporaryDirectory() as temp, patch('planner.run.generate',side_effect=responses) as model:
            result=run(make_request('Xóa khách'), 'fixture', 'http://127.0.0.1:11434',Path(temp)/'run')
            self.assertTrue(result['schema_valid'])
            self.assertEqual(result['plan'],good)
            self.assertEqual(model.call_count,2)
            self.assertEqual(result['usage'],{'input_tokens':30,'output_tokens':10})
            self.assertIn('validation_error',result['attempts'][0])
