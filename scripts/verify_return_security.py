import json
from pathlib import Path
import httpx
from dotenv import dotenv_values
from app.config import env
from app.medusa import Medusa, BackendError
fixture=json.loads(Path('reports/return-fixture.json').read_text())
report=json.loads(Path('reports/return-smoke.json').read_text())
creds=json.loads(Path('data/demo-credentials.json').read_text())
tokens=[]
for credentials in creds:
    r=httpx.post(env('MEDUSA_URL')+'/auth/customer/emailpass',json=credentials,timeout=30)
    r.raise_for_status()
    tokens.append(r.json()['token'])
body={'order_id':fixture['order_id'],'items':fixture['items'],'return_shipping':{'option_id':fixture['shipping_option_id']},'location_id':fixture['location_id']}
statuses=[]
for token in ('',tokens[1]):
    r=httpx.post(env('MEDUSA_URL')+'/store/returns',headers={'x-publishable-api-key':env('MEDUSA_PUBLISHABLE_KEY'),**({'Authorization':'Bearer '+token} if token else {})},json=body,timeout=30)
    assert r.status_code in (401,403)
    statuses.append(r.status_code)
r=httpx.post(env('MEDUSA_URL')+'/store/returns',headers={'x-publishable-api-key':env('MEDUSA_PUBLISHABLE_KEY'),'Authorization':'Bearer '+tokens[0]},json={**body,'receive_now':True},timeout=30)
assert r.status_code==400
try:
    Medusa().validate_return(fixture['order_id'],fixture['items'],tokens[0])
    raise AssertionError('Duplicate return eligibility accepted')
except BackendError:
    pass
admin=dotenv_values('../my-medusa-store/apps/backend/.env.admin')
r=httpx.post(env('MEDUSA_URL')+'/auth/user/emailpass',json={'email':admin['ADMIN_EMAIL'],'password':admin['ADMIN_PASSWORD']},timeout=30)
r.raise_for_status()
r=httpx.get(env('MEDUSA_URL')+'/admin/returns',headers={'Authorization':'Bearer '+r.json()['token']},params={'order_id':fixture['order_id']},timeout=30)
r.raise_for_status()
assert any(row['id']==report['return_id'] for row in r.json()['returns'])
report.update(direct_return_denials=statuses,receive_now_denial=400,duplicate_eligibility_denied=True,admin_persistence_verified=True)
Path('reports/return-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
