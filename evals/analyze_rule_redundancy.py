#!/usr/bin/env python3
import json,re
from pathlib import Path
STOP={'the','and','or','with','before','after','when','from','only','every','into','that','this','without'}
def toks(s):return {x for x in re.findall(r'[a-z0-9-]+',s.lower()) if len(x)>3 and x not in STOP}
def main():
 root=Path(__file__).resolve().parents[1];rules=[]
 skills=root/'plugins'/'agentic-project-lifecycle'/'skills'
 for p in skills.glob('*/SKILL.md'):
  for line in p.read_text().splitlines():
   m=re.search(r'\*\*(RULE-[A-Z]+-\d{2}):\*\* (.+)',line)
   if m:rules.append((m.group(1),toks(m.group(2))))
 pairs=[]
 for i,(a,x) in enumerate(rules):
  for b,y in rules[i+1:]:
   j=len(x&y)/len(x|y) if x|y else 0
   if j>=.55:pairs.append({'left':a,'right':b,'jaccard':round(j,3)})
 report={'rules':len(rules),'high_overlap_pairs':pairs,'pass':not pairs,'warning':'Lexical overlap is not behavioral ablation.'};out=root/'evals/results/rule-redundancy.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n');print(report);return 0 if report['pass'] else 1
if __name__=='__main__':raise SystemExit(main())
