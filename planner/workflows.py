"""Compile evidenced business intent into M0 semantic browser plans, not B0 selectors."""
import json
from .core import validate_plan
from .intent import validate as validate_intent

REQUIRED = {
    'find_customer':('customer_email',),
    'create_customer':('name','customer_email','phone'),
    'update_phone':('customer_email','phone'),
    'create_order':('customer_email',),
    'create_ticket':('order_id','subject'),
    'close_ticket':('ticket_id','note')}
QUESTIONS = {'customer_email':'Email khách hàng là gì?', 'name':'Tên khách hàng là gì?',
             'phone':'Số điện thoại cần nhập là gì?', 'order_id':'Mã đơn hàng cần liên kết là gì?',
             'ticket_id':'Mã ticket cần đóng là gì?', 'subject':'Tiêu đề ticket là gì?',
             'note':'Ghi chú đóng ticket là gì?'}
# control: (page state, action, next state). Browser controls, not benchmark answers.
CONTROLS = {
    'search_email':('customers','fill','customers'),
    'search_submit':('customers','click','customers_searched'),
    'customer_open':('customers_searched','click','customer_detail'),
    'customer_edit':('customer_detail','click','customer_edit'),
    'edit_phone':('customer_edit','fill','customer_edit'),
    'save_phone':('customer_edit','click','customer_detail'),
    'new_name':('customer_new','fill','customer_new'),
    'new_email':('customer_new','fill','customer_new'),
    'new_phone':('customer_new','fill','customer_new'),
    'save_customer':('customer_new','click','customers'),
    'order_customer':('order_new','select','order_new'),
    'add_line':('order_new','click','order_new'),
    'line_sku':('order_new','select','order_new'),
    'line_qty':('order_new','fill','order_new'),
    'save_order':('order_new','click','order_detail'),
    'ticket_order':('ticket_new','select','ticket_new'),
    'ticket_subject':('ticket_new','fill','ticket_new'),
    'save_ticket':('ticket_new','click','ticket_detail'),
    'ticket_open':('tickets','click','ticket_detail'),
    'close_note':('ticket_detail','fill','ticket_detail'),
    'close_ticket':('ticket_detail','click','ticket_detail')}
PAGES={'/customers':'customers','/customers/new':'customer_new',
       '/orders/new':'order_new','/tickets':'tickets','/tickets/new':'ticket_new'}
TARGETS={
    'search_email':'Ô tìm khách hàng theo email','search_submit':'Nút Tìm khách hàng',
    'customer_open':'Mở khách hàng theo email {value}', 'customer_edit':'Liên kết Sửa khách hàng',
    'edit_phone':'Số điện thoại trong form sửa khách hàng','save_phone':'Nút Lưu số điện thoại',
    'new_name':'Tên khách hàng mới','new_email':'Email khách hàng mới',
    'new_phone':'Số điện thoại khách hàng mới','save_customer':'Nút Lưu khách hàng mới',
    'order_customer':'Khách hàng của đơn mới','add_line':'Nút Thêm dòng sản phẩm',
    'line_sku':'Sản phẩm dòng {row}','line_qty':'Số lượng dòng {row}',
    'save_order':'Nút Xác nhận tạo đơn','ticket_order':'Đơn hàng của ticket mới',
    'ticket_subject':'Tiêu đề ticket mới','save_ticket':'Nút Gửi ticket',
    'ticket_open':'Mở ticket {value}','close_note':'Ghi chú đóng ticket',
    'close_ticket':'Nút Đóng ticket'}


# All missing fields are collected before producing any executable step.
def compile_intent(intent, request):
    validate_intent(intent,request['goal'])
    plan={'version':'0.2','status':'ready','objective':request['goal'],'entities':[],
          'questions':[],'steps':[],'verification':[]}
    workflow={'version':'1.0','steps':[],'bindings':[],'scope':'M0 known workflows; not semantic ranking'}
    ops=intent['operations']
    if any(o['kind']=='unsupported' for o in ops):
        plan['status']='unsupported'
        return {'plan':validate_plan(plan,request),'workflow':workflow}
    available=set()
    for index,op in enumerate(ops):
        kind=op['kind'];slots={s['key']:s['value'] for s in op['slots']}
        if kind=='unresolved':
            plan['questions'].append('Bạn muốn thực hiện nghiệp vụ nào và với đối tượng nào?')
            continue
        for key in REQUIRED[kind]:
            if key not in slots:
                plan['questions'].append(f'Bước nghiệp vụ {index+1}: '+QUESTIONS[key])
        for key,value in slots.items():
            if value.startswith('$') and value not in available:
                plan['questions'].append(f'Bước nghiệp vụ {index+1}: chưa có đối tượng cho tham chiếu {value}. '+QUESTIONS[key])
            plan['entities'].append({'name':f'{index+1}.{key}','value':value})
        if kind=='create_order' and not op['items']:
            plan['questions'].append(f'Bước nghiệp vụ {index+1}: SKU và số lượng từng sản phẩm là gì?')
        for row,item in enumerate(op['items'],1):
            plan['entities'].extend([{'name':f'{index+1}.item{row}.sku','value':item['sku']},
                                     {'name':f'{index+1}.item{row}.quantity','value':str(item['quantity'])}])
        if kind=='create_customer': available.add('$last_customer')
        if kind=='create_order': available.add('$last_order')
    if plan['questions']:
        plan['status']='needs_clarification'
        return {'plan':validate_plan(plan,request),'workflow':workflow}

    def go(url):
        plan['steps'].append({'action':'navigate','target':'Trang '+url,'value':'','url':url,'expected':''})
        workflow['steps'].append({'control':'navigate','url':url,'operation_index':op_index})

    def add(control,value='',row=0):
        action=CONTROLS[control][1]
        target=TARGETS[control].format(value=value,row=row)
        plan['steps'].append({'action':action,'target':target,
                              'value':str(value) if action in ('fill','select') else '',
                              'url':'','expected':''})
        workflow['steps'].append({'control':control,'argument':str(value),'row':row,'operation_index':op_index})

    for op_index,op in enumerate(ops):
        kind=op['kind'];s={v['key']:v['value'] for v in op['slots']}
        if kind in ('find_customer','update_phone'):
            go('/customers');add('search_email',s['customer_email']);add('search_submit')
            add('customer_open',s['customer_email'])
            if kind=='update_phone':
                add('customer_edit');add('edit_phone',s['phone']);add('save_phone')
        elif kind=='create_customer':
            go('/customers/new');add('new_name',s['name']);add('new_email',s['customer_email'])
            add('new_phone',s['phone']);add('save_customer')
            workflow['bindings'].append({'symbol':'$last_customer','after_step':len(plan['steps'])-1,
                                         'source':'customer_email supplied to saved customer'})
        elif kind=='create_order':
            go('/orders/new');add('order_customer',s['customer_email'])
            for row,item in enumerate(op['items'],1):
                if row>1: add('add_line')
                add('line_sku',item['sku'],row);add('line_qty',item['quantity'],row)
            add('save_order')
            workflow['bindings'].append({'symbol':'$last_order','after_step':len(plan['steps'])-1,
                                         'source':'actual order code on result page; never guessed'})
        elif kind=='create_ticket':
            go('/tickets/new');add('ticket_order',s['order_id']);add('ticket_subject',s['subject']);add('save_ticket')
        elif kind=='close_ticket':
            go('/tickets');add('ticket_open',s['ticket_id']);add('close_note',s['note']);add('close_ticket')
        desired={**s}
        if op['items']: desired['items']=[{k:v for k,v in item.items() if k!='source'} for item in op['items']]
        plan['verification'].append({'target':kind,'expected':json.dumps(desired,ensure_ascii=False,sort_keys=True)})
    validate_plan(plan,request)
    validate_workflow(plan,workflow,request,intent)
    return {'plan':plan,'workflow':workflow}


# Replay state/control preconditions independently; reject missing edits, premature submits and unbound refs.
def validate_workflow(plan, workflow, request, intent=None):
    validate_plan(plan,request)
    if len(plan['steps'])!=len(workflow['steps']): raise ValueError('Workflow/plan length mismatch')
    state=None;filled={};rows=1;bindings=set();previous_operation=-1
    if intent is not None:
        validate_intent(intent,request['goal'])
    for i,(step,meta) in enumerate(zip(plan['steps'],workflow['steps'])):
        key=meta['control']
        if intent is not None:
            index=meta.get('operation_index',-1)
            if not previous_operation<=index<len(intent['operations']): raise ValueError('Invalid operation order')
            previous_operation=index
        if key!='navigate' and key not in CONTROLS: raise ValueError('Unknown semantic control')
        if intent is not None and key!='navigate':
            op=intent['operations'][meta['operation_index']]
            slots={s['key']:s['value'] for s in op['slots']}
            inputs={'search_email':'customer_email','customer_open':'customer_email',
                    'edit_phone':'phone','new_name':'name','new_email':'customer_email','new_phone':'phone',
                    'order_customer':'customer_email','ticket_order':'order_id','ticket_subject':'subject',
                    'ticket_open':'ticket_id','close_note':'note'}
            if key in inputs and meta.get('argument')!=slots.get(inputs[key]):
                raise ValueError('Workflow input differs from evidenced intent')
            if key in ('line_sku','line_qty'):
                row=meta.get('row',0)
                if not 1<=row<=len(op['items']): raise ValueError('Row not present in intent')
                item=op['items'][row-1]
                expected=item['sku'] if key=='line_sku' else str(item['quantity'])
                if meta.get('argument')!=expected: raise ValueError('Product/quantity differs from intent')
        if key=='navigate':
            if step['action']!='navigate' or step['url']!=meta['url'] or meta['url'] not in PAGES:
                raise ValueError('Invalid navigation transition')
            state=PAGES[meta['url']];filled={};rows=1
            continue
        before,action,after=CONTROLS[key]
        value=meta.get('argument','');row=meta.get('row',0)
        if state!=before or step['action']!=action:
            raise ValueError('Control unavailable in state: '+key)
        if step['target']!=TARGETS[key].format(value=value,row=row): raise ValueError('Target/control mismatch')
        if action in ('fill','select') and step['value']!=value: raise ValueError('Value/control mismatch')
        if value.startswith('$') and value not in bindings: raise ValueError('Unbound runtime reference')
        if key=='search_submit' and 'search_email' not in filled: raise ValueError('Search requires email')
        if key=='customer_open' and value!=filled.get('search_email'): raise ValueError('Wrong customer after search')
        if key=='add_line': rows+=1
        if key in ('line_sku','line_qty') and not 1<=row<=rows: raise ValueError('Product row does not exist')
        if action in ('fill','select'): filled[(key,row) if row else key]=value
        requirements={'save_phone':['edit_phone'], 'save_customer':['new_name','new_email','new_phone'],
                      'save_ticket':['ticket_order','ticket_subject'],'close_ticket':['close_note']}
        if any(field not in filled for field in requirements.get(key,[])): raise ValueError('Submit before form is complete')
        if key=='save_customer':
            bindings.add('$last_customer')
        if key=='save_order':
            if 'order_customer' not in filled or any((field,n) not in filled for n in range(1,rows+1) for field in ('line_sku','line_qty')):
                raise ValueError('Order has missing fields or blank product rows')
            bindings.add('$last_order')
        state=after
    return plan
