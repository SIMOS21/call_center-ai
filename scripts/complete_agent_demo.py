"""Complete the confirmed local demo cart via real LLM approval and sandbox APIs."""
import json
import time
from pathlib import Path
import httpx
from app.config import env
from app.medusa import Medusa


def main():
    path=Path('reports/agent-live.json')
    report=json.loads(path.read_text(encoding='utf-8'))
    cart=report['confirmed_cart_id']
    creds=json.loads(Path('data/demo-credentials.json').read_text())[0]
    response=httpx.post(env('MEDUSA_URL')+'/auth/customer/emailpass',json=creds,timeout=30)
    response.raise_for_status()
    token=response.json()['token']
    headers={'Authorization':'Bearer '+token,'x-publishable-api-key':env('MEDUSA_PUBLISHABLE_KEY')}
    store=httpx.Client(base_url=env('MEDUSA_URL'),headers=headers,timeout=60)
    api=httpx.Client(base_url='http://127.0.0.1:8001',headers={'Authorization':'Bearer '+token},timeout=180)
    def call(method,route,**kwargs):
        response=store.request(method,route,**kwargs)
        if response.is_error:
            raise RuntimeError(f'Local Medusa {route}: HTTP {response.status_code}')
        return response.json()
    address={'first_name':'Demo','last_name':'Customer','address_1':'1 Test Street','city':'Paris','country_code':'fr','postal_code':'75001'}
    call('POST',f'/store/carts/{cart}',json={'email':creds['email'],'shipping_address':address,'billing_address':address})
    options=call('GET','/store/shipping-options',params={'cart_id':cart})['shipping_options']
    call('POST',f'/store/carts/{cart}/shipping-methods',json={'option_id':options[0]['id']})
    collection=call('POST','/store/payment-collections',json={'cart_id':cart})['payment_collection']
    call('POST',f"/store/payment-collections/{collection['id']}/payment-sessions",json={'provider_id':'pp_system_default'})
    def chat(name,prompt,expected):
        started=time.perf_counter()
        response=api.post('/chat',json={'message':prompt})
        if response.status_code!=200:
            raise RuntimeError(f'{name}: HTTP {response.status_code}')
        result=response.json()
        row={'scenario':name,'expected_tool':expected,'used_tools':result['used_tools'],'tool_calls':result['tool_calls'],'request_id':result['request_id'],'answer':result['answer'],'latency_ms':(time.perf_counter()-started)*1000,'selection_correct':expected in result['used_tools'],'escalation':result.get('escalation_recommended',False)}
        report['cases'].append(row)
        path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        assert row['selection_correct'], name
        return result
    pending=chat('checkout',f'Le panier {cart} est prêt avec livraison et paiement système de test. Demande ma confirmation explicite pour le finaliser.','request_checkout')
    approval=pending['pending_actions'][0]['approval_id']
    response=api.post('/actions/confirm',json={'approval_id':approval,'confirm':True})
    assert response.status_code==200 and response.json()['status']=='done'
    order_id=response.json()['result']['order_id']
    order=Medusa().order(order_id,token)
    report['agent_order_id']=order_id
    report['agent_order_status']=order['status']
    chat('ticket',f'Crée un ticket de catégorie delivery pour ma commande {order_id}. Description : demande de suivi de démonstration technique de la boutique locale.','create_ticket')
    tickets=api.get('/tickets').json()['tickets']
    assert any(t['order_id']==order_id for t in tickets)
    report['ticket_persisted']=True
    report['financial_payment']=False
    cases=report['cases']
    report['metrics']={'n_scenarios':len(cases),'tool_selection_accuracy':sum(x['selection_correct'] for x in cases)/len(cases),'mean_tool_calls':sum(x['tool_calls'] for x in cases)/len(cases),'mean_latency_ms':sum(x['latency_ms'] for x in cases)/len(cases)}
    report['limitation']='Six guided development scenarios on generated test data. No independent test-set claim. Authorized return and token/cost metrics not evaluated.'
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    import mlflow
    mlflow.set_tracking_uri(env('MLFLOW_TRACKING_URI'))
    mlflow.set_experiment('commerceops-agent-live')
    with mlflow.start_run(run_name='nvidia-vertical-checkout-ticket') as run:
        mlflow.log_params({'provider':'NVIDIA','model':env('LLM_MODEL'),'payment':'pp_system_default','scenarios':'guided_development'})
        mlflow.log_metrics(report['metrics'])
        mlflow.log_artifact(str(path))
        report['vertical_mlflow_run_id']=run.info.run_id
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('VERTICAL DEMO PASS',order_id,report['metrics'])


if __name__=='__main__':
    main()
