import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from adapter import total_cents
assert total_cents(100,20)==120
print('brownfield smoke: pass')
