#!/usr/bin/env python3
import json,re
from pathlib import Path
def main():
 root=Path(__file__).parent;cov=json.loads((root/'rule-coverage.json').read_text())['rules'];decl=[]
 skills=root.parent/'plugins'/'agentic-project-lifecycle'/'skills'
 for p in skills.glob('*/SKILL.md'):decl+=re.findall(r'RULE-[A-Z]+-\d{2}',p.read_text())
 owned={r['id'] for r in cov if r.get('assertions')};report={'declared':len(decl),'owned':len(owned),'missing':sorted(set(decl)-owned),'extra':sorted(owned-set(decl)),'pass':set(decl)==owned};(root/'results').mkdir(exist_ok=True);(root/'results/static-ablation-report.json').write_text(json.dumps(report,indent=2)+'\n');print(report);return 0 if report['pass'] else 1
if __name__=='__main__':raise SystemExit(main())
