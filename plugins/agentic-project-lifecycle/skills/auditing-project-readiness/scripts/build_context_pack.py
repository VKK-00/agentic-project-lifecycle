#!/usr/bin/env python3
from __future__ import annotations
import argparse,shutil,yaml
from pathlib import Path

def safe(root:Path,rel:str)->Path:
    if Path(rel).is_absolute():raise ValueError(f'absolute path forbidden: {rel}')
    resolved=(root/rel).resolve()
    if root.resolve() not in resolved.parents and resolved!=root.resolve():raise ValueError(f'path traversal forbidden: {rel}')
    return resolved

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.root.resolve();m=yaml.safe_load(a.manifest.read_text(encoding='utf-8'));a.output.mkdir(parents=True,exist_ok=True)
    copied=[]
    for rel in m.get('read',[]):
        source=safe(root,rel)
        if not source.is_file():raise SystemExit(f'missing context file: {rel}')
        dest=a.output/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);copied.append(rel)
    shutil.copy2(a.manifest,a.output/'context-manifest.yaml')
    packet=['# Task packet','',f"**Task:** {m.get('task','unknown')}",f"**Goal:** {m.get('goal','')}",'','## Read']+[f'- `{x}`' for x in copied]+['','## Allowed paths']+[f'- `{x}`' for x in m.get('allowed_paths',[])]+['','## Forbidden paths']+[f'- `{x}`' for x in m.get('forbidden_paths',[])]+['','## Verification']+[f'- `{x}`' for x in m.get('required_commands',[])]+['','## Decisions not to reopen']+[f'- `{x}`' for x in m.get('decisions_not_to_reopen',[])]
    (a.output/'task-packet.md').write_text('\n'.join(packet)+'\n',encoding='utf-8')
    print(f'CONTEXT PACK: PASS ({len(copied)} source files)');return 0
if __name__=='__main__':raise SystemExit(main())
