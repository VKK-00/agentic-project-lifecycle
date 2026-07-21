import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from adapter import total_cents
from legacy import legacy_total
class Tests(unittest.TestCase):
 def test_contract(self):
  for s,t in [(0,20),(100,0),(100,20),(999,7)]:self.assertEqual(total_cents(s,t),legacy_total(s,t))
 def test_negative(self):
  with self.assertRaises(ValueError):total_cents(-1,20)
