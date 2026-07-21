#!/usr/bin/env python3
from __future__ import annotations
import argparse, sys, yaml
from pathlib import Path

PHASES={'orientation','discovery','specification','solution-design','planning','implementation','release','operations'}
STATUSES={'blocked','in-progress','review','ready','complete'}

def validate(path:Path):
    errors=[]
    try:data=yaml.safe_load(path.read_text(encoding='utf-8'))
    except Exception as e:return [f'cannot parse YAML: {e}']
    if not isinstance(data,dict):return ['root must be a mapping']
    project=data.get('project',{});life=data.get('lifecycle',{});outcome=data.get('current_outcome',{})
    for key in ('id','name','type','mode'):
        if not project.get(key):errors.append(f'project.{key} is required')
    if life.get('current_phase') not in PHASES:errors.append('lifecycle.current_phase is invalid')
    if life.get('status') not in STATUSES:errors.append('lifecycle.status is invalid')
    for key in ('id','statement','metric','target'):
        if outcome.get(key) in (None,''):errors.append(f'current_outcome.{key} is required')
    blockers=data.get('blockers',[]) or []
    for b in blockers:
        if not b.get('id') or not b.get('reason'):errors.append('every blocker needs id and reason')
        if not b.get('owner'):errors.append(f"unowned blocker: {b.get('id','unknown')}")
    if life.get('status')=='ready' and blockers:errors.append('ready state cannot contain blockers')
    artifacts=data.get('artifacts',{})
    phase=life.get('current_phase')
    required={'specification':['charter','prd'],'solution-design':['charter','prd','design'],'planning':['charter','prd','design','plan'],'implementation':['charter','prd','design','plan'],'release':['charter','prd','design','plan','evidence','release_plan','runbook'],'operations':['charter','prd','design','plan','evidence','release_plan','runbook']}.get(phase,[])
    for name in required:
        if artifacts.get(name) not in {'approved','verified','complete'}:errors.append(f'artifact {name} is not approved/verified')
    return errors

def main():
    p=argparse.ArgumentParser();p.add_argument('path',type=Path);a=p.parse_args();errors=validate(a.path)
    if errors:
        print('PROJECT STATE: FAIL');[print(f'- {e}') for e in errors];return 1
    print('PROJECT STATE: PASS');return 0
if __name__=='__main__':raise SystemExit(main())
