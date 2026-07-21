import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from saas import Workspace
class Tests(unittest.TestCase):
 def test_free_blocks_second_member(self):
  with self.assertRaises(PermissionError):Workspace('owner').invite('member')
 def test_pro_allows_member(self):
  w=Workspace('owner','pro');w.invite('member');self.assertIn('member',w.members)
