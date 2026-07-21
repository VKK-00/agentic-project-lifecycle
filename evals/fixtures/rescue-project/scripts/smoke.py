import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from queue_service import process
assert process([' job '])==['job']
print('rescue smoke: pass')
