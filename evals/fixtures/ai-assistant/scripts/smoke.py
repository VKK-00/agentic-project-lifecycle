import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from extractor import extract
assert len(extract('Action: verify'))==1
print('ai smoke: pass')
