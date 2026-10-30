"""Isolated M0 feasibility harness. Fixed accessibility adapter, not a ranking benchmark."""
import argparse
import json
import re
import socket
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote
import httpx
import uvicorn
from playwright.sync_api import sync_playwright
from app import db
from app.seed import reset_database
from .workflows import validate_workflow


# In-process test server avoids orphaning Windows venv launcher child processes.
@contextmanager
def isolated_m0():
    original=db.DB_PATH
    with tempfile.TemporaryDirectory(prefix='planner-m0-') as temp:
        db.DB_PATH=Path(temp)/'test.sqlite3';reset_database()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        server=uvicorn.Server(uvicorn.Config('app.main:app',host='127.0.0.1',port=port,log_level='error'))
        thread=threading.Thread(target=server.run,daemon=True);thread.start()
        try:
            for _ in range(100):
                if server.started: break
                if not thread.is_alive(): raise RuntimeError('M0 server exited')
                time.sleep(.1)
            else: raise RuntimeError('M0 server startup timed out')
            yield base
        finally:
            server.should_exit=True;thread.join(10)
            db.DB_PATH=original
            if thread.is_alive(): raise RuntimeError('M0 server did not stop')


# Resolve semantic controls against known M0 labels; fail on ambiguity rather than choosing first.
def execute(page, base, bundle):
    plan,workflow=bundle['plan'],bundle['workflow']
    validate_workflow(plan,workflow,bundle['request'],bundle['intent'])
    if plan['status']!='ready': raise ValueError('Only ready plans may execute')
    bindings={};completed=[];created_orders=[];created_tickets=[];operation_refs={}
    page.set_default_timeout(5000)
    def value(v):
        if v.startswith('$'):
            if v not in bindings: raise ValueError('Unbound runtime reference: '+v)
            return bindings[v]
        return v
    for step,meta in zip(plan['steps'],workflow['steps']):
        key=meta['control'];arg=value(meta.get('argument',''));row=meta.get('row',0)
        if key=='navigate': page.goto(base+step['url'])
        elif key in ('search_email','new_name','new_email','new_phone','edit_phone','close_note','ticket_subject'):
            label={'search_email':'Tìm khách hàng theo email','new_name':'Tên khách hàng','new_email':'Email',
                   'new_phone':'Số điện thoại','edit_phone':'Số điện thoại',
                   'close_note':'Ghi chú','ticket_subject':'Tiêu đề'}[key]
            page.get_by_label(label,exact=True).fill(arg)
            if key=='new_email': bindings['$pending_customer']=arg
        elif key=='customer_open':
            page.get_by_role('row').filter(has=page.get_by_role('cell',name=arg,exact=True)).get_by_role('link').click()
        elif key=='customer_edit': page.get_by_role('link',name='Sửa',exact=True).click()
        elif key=='order_customer':
            select=page.get_by_label('Khách hàng',exact=True)
            option=select.get_by_role('option').filter(has_text=arg)
            if option.count()!=1: raise ValueError('Customer option must be unique')
            select.select_option(value=option.get_attribute('value'))
        elif key in ('line_sku','line_qty'):
            line=page.get_by_role('group',name=f'Sản phẩm {row}',exact=True)
            if key=='line_qty': line.get_by_label('Số lượng',exact=True).fill(arg)
            else:
                select=line.get_by_label('Sản phẩm',exact=True)
                select.select_option(value=arg)
        elif key=='ticket_order': page.get_by_label('Đơn hàng',exact=True).select_option(value=arg)
        elif key=='ticket_open': page.get_by_role('link',name=arg,exact=True).click()
        else:
            label={'search_submit':'Tìm','save_phone':'Lưu','save_customer':'Lưu',
                   'add_line':'Thêm dòng','save_order':'Xác nhận tạo đơn',
                   'save_ticket':'Gửi','close_ticket':'Đóng ticket'}[key]
            page.get_by_role('button',name=label,exact=True).click()
        if key=='save_customer':
            # Only bind after the save redirected to the list without a form error.
            if page.url.split('?')[0]!=base+'/customers': raise ValueError('Customer was not saved')
            bindings['$last_customer']=bindings.pop('$pending_customer')
        if key=='save_order':
            match=re.fullmatch(r'Đơn hàng (ORD-\d+)',page.get_by_role('heading',level=1).inner_text())
            if not match: raise ValueError('Order result code missing')
            bindings['$last_order']=match[1];created_orders.append(match[1])
        if key=='save_ticket':
            match=re.fullmatch(r'Ticket (TCK-\d+)',page.get_by_role('heading',level=1).inner_text())
            if not match: raise ValueError('Ticket result code missing')
            created_tickets.append(match[1])
        completed.append({'index':len(completed),'control':key,'url':page.url})
        operation_refs[meta['operation_index']]=bindings.copy()

    # Read persisted API state after browser mutations. Expected values come from the intent, not snapshots.
    checks=[];order_i=ticket_i=0
    with httpx.Client(base_url=base,trust_env=False,timeout=10) as api:
        def get(path):
            r=api.get(path);r.raise_for_status();return r.json()
        for op_index,op in enumerate(bundle['intent']['operations']):
            refs=operation_refs.get(op_index,{})
            kind=op['kind'];s={v['key']:refs[v['value']] if v['value'].startswith('$') else v['value'] for v in op['slots']}
            ok=False
            if kind in ('create_customer','find_customer','update_phone'):
                data=get('/api/customers?email='+quote(s['customer_email']))
                customers=data['customers'];ok=len(customers)==1
                if ok and kind=='create_customer': ok=customers[0]['name']==s['name'] and customers[0]['phone']==s['phone']
                if ok and kind=='update_phone': ok=customers[0]['phone']==s['phone']
            elif kind=='create_order':
                data=get('/api/orders/'+created_orders[order_i]);order_i+=1
                actual=sorted((v['sku'],v['qty']) for v in data['items'])
                expected=sorted((v['sku'],v['quantity']) for v in op['items'])
                ok=data['customer_email']==s['customer_email'] and actual==expected
            elif kind=='create_ticket':
                data=get('/api/tickets/'+created_tickets[ticket_i]);ticket_i+=1
                ok=data['subject']==s['subject'] and data['order_id']==s['order_id']
            elif kind=='close_ticket':
                data=get('/api/tickets/'+s['ticket_id'])
                ok=data['status']=='closed' and data['note']==s['note']
            checks.append({'kind':kind,'persisted_state_matches_intent':ok})
    return {'scope':'M0 fixed accessibility adapter; not ranking, mutation or general agent success',
            'steps':completed,'bindings':bindings,'checks':checks,
            'persisted_state_matches_intent':all(c['persisted_state_matches_intent'] for c in checks)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();bundle=json.loads(args.trace.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True,exist_ok=False)
    try:
        with isolated_m0() as base, sync_playwright() as pw:
            browser=pw.chromium.launch()
            try:
                with browser.new_context() as ctx:
                    result=execute(ctx.new_page(),base,bundle)
            finally: browser.close()
    except Exception as exc:
        result={'error':f'{type(exc).__name__}: {exc}','persisted_state_matches_intent':False}
    result['trace_sha256']=__import__('hashlib').sha256(args.trace.read_bytes()).hexdigest()
    (args.output/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['persisted_state_matches_intent'] else 1


if __name__=='__main__': raise SystemExit(main())
