"""Real local authorized return; no receipt or financial refund."""
import json
from pathlib import Path
import httpx
from app.config import env
from app.agent import Agent
from app.medusa import Medusa

fixture=json.loads(Path('reports/return-fixture.json').read_text())
creds=json.loads(Path('data/demo-credentials.json').read_text())
tokens=[]
for customer in creds:
    response=httpx.post(env('MEDUSA_URL')+'/auth/customer/emailpass',json=customer,timeout=30)
    response.raise_for_status()
    tokens.append(response.json()['token'])
m=Medusa()
order=m.validate_return(fixture['order_id'],fixture['items'],tokens[0])
args={key:fixture[key] for key in ('order_id','items','shipping_option_id','location_id')}
# Tool request is local and uses only the configured store policy, not RAG consent.
approval=Agent(m)._observed_tool('request_return',args,tokens[0],'return-integration')
assert approval.get('approval_id'), approval
api=httpx.Client(base_url='http://127.0.0.1:8001',timeout=90)
body={'approval_id':approval['approval_id'],'confirm':True}
assert api.post('/actions/confirm',json=body,headers={'Authorization':'Bearer '+tokens[1]}).status_code==404
response=api.post('/actions/confirm',json=body,headers={'Authorization':'Bearer '+tokens[0]})
if response.status_code!=200:
    raise RuntimeError(f'Return HTTP {response.status_code}: '+str(response.json().get('detail')))
result=response.json()
assert result['status']=='done' and result['result']['return_id']
assert result['result']['financial_refund'] is False
repeat=api.post('/actions/confirm',json=body,headers={'Authorization':'Bearer '+tokens[0]})
assert repeat.status_code==409
report={'status':'PASS','order_id':fixture['order_id'],'return_id':result['result']['return_id'],'return_status':'requested','financial_refund':False,'receive_now':False,'repeat_confirmation_status':409,'foreign_confirmation_status':404}
Path('reports/return-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
