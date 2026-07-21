import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from extractor import Action,extract
class Tests(unittest.TestCase):
 def test_explicit_only(self):self.assertEqual(extract('Note: discuss\nAction: prepare'),[Action('prepare')])
