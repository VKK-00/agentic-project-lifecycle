#!/usr/bin/env python3
from __future__ import annotations
import argparse,yaml
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('path',type=Path);a=p.parse_args();errors=[]
    try:d=yaml.safe_load(a.path.read_text(encoding='utf-8'))
    except Exception as e:print(f'TRACEABILITY: FAIL\n- cannot parse YAML: {e}');return 1
    reqs=d.get('requirements',{}) or {};features=d.get('features',{}) or {};tests=d.get('tests',{}) or {};evidence=d.get('evidence',{}) or {};releases=d.get('releases',{}) or {}
    if not reqs:errors.append('requirements are empty')
    for rid,r in reqs.items():
        for field in ('implemented_by','verified_by','released_in'):
            if not r.get(field):errors.append(f'{rid}.{field} is empty')
        for fid in r.get('implemented_by',[]):
            if fid not in features:errors.append(f'{rid} references missing feature {fid}')
        for tid in r.get('verified_by',[]):
            if tid not in tests:errors.append(f'{rid} references missing test {tid}')
        for rel in r.get('released_in',[]):
            if rel not in releases:errors.append(f'{rid} references missing release {rel}')
    for fid,f in features.items():
        if not f.get('acceptance_criteria'):errors.append(f'{fid}.acceptance_criteria is empty')
    for tid,t in tests.items():
        eid=t.get('evidence')
        if not eid:errors.append(f'{tid}.evidence is empty')
        elif eid not in evidence:errors.append(f'{tid} references missing evidence {eid}')
    if errors:
        print('TRACEABILITY: FAIL');[print(f'- {e}') for e in errors];return 1
    print(f'TRACEABILITY: PASS ({len(reqs)} requirements)');return 0
if __name__=='__main__':raise SystemExit(main())
