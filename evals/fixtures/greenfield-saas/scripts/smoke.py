import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from saas import Workspace
w=Workspace('owner','pro');w.invite('member');assert len(w.members)==2
print('saas smoke: pass')
