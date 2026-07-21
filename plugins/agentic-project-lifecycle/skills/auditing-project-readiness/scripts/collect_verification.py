#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,time,yaml,hashlib
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();cfg=yaml.safe_load(a.config.read_text(encoding='utf-8'));a.output.mkdir(parents=True,exist_ok=True);checks=[]
    for item in cfg.get('commands',[]):
        name=item['name'];argv=item['run'];started=time.monotonic();result=subprocess.run(argv,cwd=a.root,text=True,capture_output=True,check=False,timeout=item.get('timeout_seconds',90));duration=round((time.monotonic()-started)*1000);log=(result.stdout or '')+(result.stderr or '');log_path=a.output/f'{name}.log';log_path.write_text(log,encoding='utf-8');checks.append({'name':name,'argv':argv,'exit_code':result.returncode,'duration_ms':duration,'log':log_path.name,'log_sha256':hashlib.sha256(log.encode()).hexdigest()})
    report={'checks':checks,'summary':{'passed':sum(x['exit_code']==0 for x in checks),'failed':sum(x['exit_code']!=0 for x in checks)}};(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report['summary']));return 0 if report['summary']['failed']==0 else 1
if __name__=='__main__':raise SystemExit(main())
