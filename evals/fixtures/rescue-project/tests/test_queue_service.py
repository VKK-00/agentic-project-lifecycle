import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from queue_service import process
class Tests(unittest.TestCase):
 def test_order(self):self.assertEqual(process([' first ','','second']),['first','second'])
