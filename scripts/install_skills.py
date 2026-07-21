#!/usr/bin/env python3
from __future__ import annotations
import argparse, shutil
from pathlib import Path

SKILLS_ROOT = (
    Path(__file__).resolve().parents[1]
    / 'plugins'
    / 'agentic-project-lifecycle'
    / 'skills'
)

def main():
    p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True);p.add_argument('--force',action='store_true');a=p.parse_args()
    a.target.mkdir(parents=True,exist_ok=True)
    for source in sorted(SKILLS_ROOT.iterdir()):
        if not source.is_dir():continue
        dest=a.target/source.name
        if dest.exists():
            if not a.force:raise SystemExit(f'refusing to overwrite {dest}; pass --force')
            shutil.rmtree(dest)
        shutil.copytree(source,dest);print(f'installed {source.name} -> {dest}')
if __name__=='__main__':main()
