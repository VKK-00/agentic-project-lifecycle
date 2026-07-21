from dataclasses import dataclass,field
@dataclass
class Workspace:
    owner_id:str
    plan:str='free'
    members:set[str]=field(default_factory=set)
    def __post_init__(self):self.members.add(self.owner_id)
    def invite(self,user_id:str):
        limit={'free':1,'pro':5}.get(self.plan,0)
        if len(self.members)>=limit:raise PermissionError('plan member limit reached')
        self.members.add(user_id)
