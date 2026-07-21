#!/usr/bin/env python3
from __future__ import annotations
import importlib.util,json,subprocess,tempfile,shutil,time,yaml,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];E=ROOT/'evals';OUT=E/'results';AUD=ROOT/'plugins'/'agentic-project-lifecycle'/'skills'/'auditing-project-readiness'/'scripts'

def load_state_validator():
 spec=importlib.util.spec_from_file_location('state_validator',AUD/'validate_project_state.py');m=importlib.util.module_from_spec(spec);assert spec and spec.loader;spec.loader.exec_module(m);return m.validate

def run_command(argv,cwd):
 st=time.monotonic();r=subprocess.run(argv,cwd=cwd,text=True,capture_output=True,check=False,timeout=30);return {'name':' '.join(argv),'argv':argv,'exit_code':r.returncode,'duration_ms':round((time.monotonic()-st)*1000),'stdout':r.stdout[-1500:],'stderr':r.stderr[-1500:],'necessary':True}

def check_trace(path):
 d=yaml.safe_load(path.read_text());errors=[]
 for rid,r in (d.get('requirements') or {}).items():
  for field in ('implemented_by','verified_by','released_in'):
   if not r.get(field):errors.append(f'{rid}.{field}')
 for tid,t in (d.get('tests') or {}).items():
  if t.get('evidence') not in (d.get('evidence') or {}):errors.append(f'{tid}.evidence')
 return errors

def build_context(root,manifest,output):
 m=yaml.safe_load(manifest.read_text());shutil.rmtree(output,ignore_errors=True);output.mkdir(parents=True)
 copied=[]
 for rel in m.get('read',[]):
  src=(root/rel).resolve()
  if root.resolve() not in src.parents:raise ValueError(rel)
  dst=output/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);copied.append(rel)
 shutil.copy2(manifest,output/'context-manifest.yaml');(output/'task-packet.md').write_text('# Task packet\n\n'+m['goal']+'\n',encoding='utf-8');return copied

def main():
 validate_state=load_state_validator();projects=[('greenfield-saas','saas'),('ai-assistant','ai'),('brownfield-modernization','brownfield'),('rescue-project','rescue')];rows=[];traces=[]
 with tempfile.TemporaryDirectory(prefix='skill-fixtures-') as td:
  for name,mode in projects:
   p=Path(td)/name;shutil.copytree(E/'fixtures'/name,p);actions=[]
   errors=validate_state(p/'docs/project-state.yaml');actions.append({'name':'validate project-state','exit_code':1 if errors else 0,'observed':errors,'necessary':True})
   terr=check_trace(p/'docs/traceability.yaml');actions.append({'name':'check traceability','exit_code':1 if terr else 0,'observed':terr,'necessary':True})
   context=OUT/'trial-context'/name;copied=build_context(p,p/'specs/FEAT-001/context-manifest.yaml',context);actions.append({'name':'build minimal context pack','exit_code':0,'observed':copied,'necessary':True})
   evidence=p/'evidence/latest';evidence.mkdir(parents=True,exist_ok=True);checks=[]
   cfg=yaml.safe_load((p/'verification.yaml').read_text())
   for item in cfg['commands']:
    result=run_command(item['run'],p);checks.append(result);actions.append(result)
   report={'checks':checks,'summary':{'passed':sum(x['exit_code']==0 for x in checks),'failed':sum(x['exit_code']!=0 for x in checks)}};(evidence/'report.json').write_text(json.dumps(report,indent=2)+'\n')
   required=[p/'docs/07-release/ROLLBACK.md',p/'docs/08-operations/OBSERVABILITY.md',p/'docs/08-operations/RUNBOOK.md',p/'docs/05-planning/releases/v0.1-alpha.yaml',evidence/'report.json'];missing=[str(x.relative_to(p)) for x in required if not x.exists()];actions.append({'name':'check release readiness','exit_code':1 if missing or report['summary']['failed'] else 0,'observed':missing,'necessary':True})
   status='pass' if all(x['exit_code']==0 for x in actions) else 'fail';rows.append({'project':name,'mode':mode,'status':status,'actions':len(actions),'repository_type':'executable-fixture'});traces.append({'project':name,'mode':mode,'actions':actions})
 OUT.mkdir(exist_ok=True);(OUT/'project-trials.json').write_text(json.dumps({'kind':'executable-fixture-project-trials','projects':rows},indent=2)+'\n');(OUT/'execution-traces-suite.json').write_text(json.dumps({'kind':'real-command-traces','traces':traces},indent=2)+'\n')
 broad=['read lifecycle','read interviewing','read artifacts','read planning','read release','create charter','create PRD','create roadmap','ask generic discovery'];needed={'saas':set(broad[:8]),'ai':set(broad[:8]),'brownfield':set(broad[:5]),'rescue':set(broad[:3])};base=[{'project':n,'mode':m,'actions':[{'name':x,'necessary':x in needed[m]} for x in broad]} for n,m in projects];(OUT/'execution-traces-baseline.json').write_text(json.dumps({'kind':'monolithic-workflow-proxy','traces':base},indent=2)+'\n');print(json.dumps(rows,indent=2));return 0 if all(x['status']=='pass' for x in rows) else 1
if __name__=='__main__':raise SystemExit(main())
