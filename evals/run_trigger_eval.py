#!/usr/bin/env python3
from __future__ import annotations
import json,hashlib,yaml
from pathlib import Path
from trigger_router import classify
SKILLS={'orchestrating-large-projects','building-saas-products','building-ai-products','modernizing-existing-projects','rescuing-software-projects','releasing-and-operating-products','auditing-project-readiness'}
def run(path):
 rows=[];tp=fp=fn=tn=0
 for c in yaml.safe_load(path.read_text(encoding='utf-8'))['cases']:
  e=set(c['expected_skills']);o=classify(c['prompt']);rows.append({'id':c['id'],'prompt':c['prompt'],'expected':sorted(e),'observed':sorted(o),'pass':e==o})
  for s in SKILLS:
   if s in e and s in o:tp+=1
   elif s not in e and s in o:fp+=1
   elif s in e and s not in o:fn+=1
   else:tn+=1
 return {'cases':rows,'exact_accuracy':sum(r['pass'] for r in rows)/len(rows),'precision':tp/(tp+fp) if tp+fp else 1,'recall':tp/(tp+fn) if tp+fn else 1,'false_positive_rate':fp/(fp+tn) if fp+tn else 0,'tp':tp,'fp':fp,'fn':fn,'tn':tn}
def main():
 root=Path(__file__).parent;report={'kind':'deterministic-routing-proxy','warning':'This does not replace provider-observed model activation.','router_sha256':hashlib.sha256((root/'trigger_router.py').read_bytes()).hexdigest(),'development':run(root/'trigger-development.yaml'),'heldout':run(root/'trigger-heldout.yaml')};(root/'results').mkdir(exist_ok=True);(root/'results/trigger-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');h=report['heldout'];print(json.dumps({k:v for k,v in h.items() if k!='cases'},indent=2));[print('FAIL',r['id'],r['expected'],r['observed']) for r in h['cases'] if not r['pass']];return 0 if h['recall']>=.95 and h['false_positive_rate']<=.05 and h['exact_accuracy']>=.9 else 1
if __name__=='__main__':raise SystemExit(main())
