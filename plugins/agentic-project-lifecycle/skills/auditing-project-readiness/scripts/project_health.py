#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--format',choices=['json','markdown'],default='markdown');a=p.parse_args();root=a.root;checks=[]
    scripts=Path(__file__).parent
    for name,argv in [('project-state',[sys.executable,str(scripts/'validate_project_state.py'),str(root/'docs/project-state.yaml')]),('traceability',[sys.executable,str(scripts/'check_traceability.py'),str(root/'docs/traceability.yaml')])]:
        r=subprocess.run(argv,text=True,capture_output=True,check=False);checks.append({'name':name,'pass':r.returncode==0,'output':(r.stdout+r.stderr).strip()})
    status='GREEN' if all(x['pass'] for x in checks) else 'RED';report={'status':status,'checks':checks}
    print(json.dumps(report,indent=2) if a.format=='json' else '# Project health\n\nOverall: **'+status+'**\n\n'+'\n'.join(f"- {x['name']}: {'PASS' if x['pass'] else 'FAIL'}" for x in checks));return 0 if status=='GREEN' else 1
if __name__=='__main__':raise SystemExit(main())
