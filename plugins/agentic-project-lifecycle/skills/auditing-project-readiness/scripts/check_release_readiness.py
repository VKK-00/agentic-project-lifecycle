#!/usr/bin/env python3
from __future__ import annotations
import argparse,yaml
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--release',required=True);a=p.parse_args();errors=[];path=a.root/f'docs/05-planning/releases/{a.release}.yaml'
    if not path.is_file():errors.append(f'missing release plan: {path.relative_to(a.root)}');data={}
    else:data=yaml.safe_load(path.read_text(encoding='utf-8'))
    fields=['version','stage','owner','support_owner','audience','hypothesis','included','excluded','entry_criteria','exit_criteria','metrics','known_limitations','rollout','rollback']
    for f in fields:
        if not data.get(f):errors.append(f'release field missing: {f}')
    required_files=['docs/07-release/ROLLBACK.md','docs/08-operations/OBSERVABILITY.md','docs/08-operations/RUNBOOK.md']
    for rel in required_files:
        if not (a.root/rel).is_file():errors.append(f'missing {rel}')
    evidence=a.root/'evidence/latest/report.json'
    if not evidence.is_file():errors.append('missing evidence/latest/report.json')
    else:
        import json
        r=json.loads(evidence.read_text());
        if r.get('summary',{}).get('failed',1)!=0:errors.append('verification evidence contains failures')
    if errors:
        print('RELEASE READINESS: FAIL');[print(f'- {e}') for e in errors];return 1
    print('RELEASE READINESS: PASS');return 0
if __name__=='__main__':raise SystemExit(main())
