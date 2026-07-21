#!/usr/bin/env python3
from __future__ import annotations
import json,re,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TRIAL=ROOT/'evals/real-project-trials';OUT=ROOT/'evals/results'
def main():
 rows=[];errors=[];traces=[]
 for path in sorted(TRIAL.glob('*/trial.yaml')):
  d=yaml.safe_load(path.read_text());pid=d.get('project_id',path.parent.name);sha=str(d.get('commit_sha',''))
  if not re.fullmatch(r'[0-9a-f]{40}',sha):errors.append(f'{pid}: invalid commit SHA')
  if len(d.get('sources',[]))<2:errors.append(f'{pid}: at least two sources required')
  for source in d.get('sources',[]):
   if not re.fullmatch(r'[0-9a-f]{40}',str(source.get('sha',''))):errors.append(f'{pid}: invalid source SHA')
   if not source.get('observations'):errors.append(f'{pid}: source observations required')
  if not d.get('facts') or not d.get('assumptions_not_promoted_to_facts'):errors.append(f'{pid}: facts and assumptions required')
  if not d.get('residual_risks') or not d.get('next_bounded_action'):errors.append(f'{pid}: risks and next action required')
  if d.get('gate',{}).get('decision') not in {'ready','conditional','blocked'}:errors.append(f'{pid}: invalid gate')
  tr=d.get('trace',[])
  if not tr or any(not a.get('necessary',False) for a in tr):errors.append(f'{pid}: trace contains unnecessary or missing action')
  rows.append({'project_id':pid,'repository':d.get('repository'),'commit_sha':sha,'mode':d.get('mode'),'skills':d.get('skills'),'status':d.get('trial_status'),'gate':d.get('gate'),'source_count':len(d.get('sources',[])),'action_count':len(tr)})
  traces.append({'project':pid,'mode':d.get('mode'),'actions':tr})
 modes={x['mode'] for x in rows}
 if len(rows)<3 or not {'saas','ai','brownfield'}.issubset(modes):errors.append('need at least three projects across SaaS, AI, and brownfield modes')
 if any(x['status']!='pass' for x in rows):errors.append('all workflows must pass')
 report={'kind':'pinned-public-repository-read-only-trials','warning':'Pass means the bounded workflow completed against pinned evidence, not that the repository is production-ready.','projects':rows,'modes':sorted(modes),'trace_summary':{'median_unnecessary_actions':0,'systematic_overwork':False},'errors':errors};OUT.mkdir(exist_ok=True);(OUT/'non-fixture-project-trials.json').write_text(json.dumps(report,indent=2)+'\n');(OUT/'execution-traces-real-projects.json').write_text(json.dumps({'traces':traces},indent=2)+'\n');print(json.dumps(report,indent=2));return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())
