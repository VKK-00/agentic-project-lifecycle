#!/usr/bin/env python3
import json,statistics
from pathlib import Path
def main():
 r=Path(__file__).parent/'results';suite=json.loads((r/'execution-traces-suite.json').read_text())['traces'];base=json.loads((r/'execution-traces-baseline.json').read_text())['traces'];sc=[sum(not a.get('necessary',False) for a in t['actions']) for t in suite];bc=[sum(not a.get('necessary',False) for a in t['actions']) for t in base];report={'kind':'trace-analysis','suite':{'trials':len(sc),'median_unnecessary_actions':statistics.median(sc),'counts':sc},'baseline':{'trials':len(bc),'median_unnecessary_actions':statistics.median(bc),'counts':bc},'systematic_overwork':statistics.median(sc)>0,'warning':'Baseline is a documented monolithic-workflow proxy; suite traces are executed commands.'};(r/'trace-analysis.json').write_text(json.dumps(report,indent=2)+'\n');print(report);return 1 if report['systematic_overwork'] else 0
if __name__=='__main__':raise SystemExit(main())
