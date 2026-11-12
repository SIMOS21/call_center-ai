"""Measure the actual dense index on the same development annotations."""
import json
import os
import statistics
import time
from pathlib import Path
import mlflow
from app import rag
from app.config import env

os.environ['RAG_BACKEND']='chroma'
cases=[json.loads(line) for line in Path('evaluation/retrieval_cases.jsonl').read_text(encoding='utf-8-sig').splitlines() if line]
rag.dense_components()
latencies=[]
hits=0
predictions=[]
for case in cases:
    expected='https://raw.githubusercontent.com/asappresearch/abcd/master/data/guidelines.json#flow='+case['flow']+'&subflow='+case['subflow']
    rag.search(case['question'])
    started=time.perf_counter()
    rows=rag.search(case['question'])
    latencies.append((time.perf_counter()-started)*1000)
    hit=any(row['source']==expected for row in rows)
    hits+=hit
    predictions.append({'question':case['question'],'expected_source':expected,'hit_at_5':hit,'sources':[row['source'] for row in rows]})
unknown=rag.search('astrophysics quasar gravitational')
metrics={'recall_at_5':hits/len(cases),'n_annotated':len(cases),'mean_retrieval_ms':statistics.mean(latencies),'p95_retrieval_ms':sorted(latencies)[int(.95*(len(latencies)-1))],'unknown_results':len(unknown)}
report={'backend':'chroma','model':env('EMBEDDING_MODEL'),'revision':env('EMBEDDING_REVISION'),'annotation':'agent_reviewed_not_human_validated','metrics':metrics,'predictions':predictions,'distance':'cosine','min_score':.3}
mlflow.set_tracking_uri(env('MLFLOW_TRACKING_URI'))
mlflow.set_experiment('commerceops-rag-development')
with mlflow.start_run(run_name='dense-multilingual-90') as run:
    mlflow.log_params({'backend':'chroma','embedding_model':report['model'],'revision':report['revision'],'chunk_words':90,'overlap_words':20,'top_k':5,'min_score':.3,'annotation':report['annotation']})
    mlflow.log_metrics(metrics)
    report['mlflow_run_id']=run.info.run_id
    Path('reports/dense-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    mlflow.log_artifact('reports/dense-evaluation.json')
p=Path('reports/evaluation.json')
combined=json.loads(p.read_text(encoding='utf-8'))
combined['dense']=report
p.write_text(json.dumps(combined,indent=2,ensure_ascii=False),encoding='utf-8')
print('DENSE MEASURED',metrics)
