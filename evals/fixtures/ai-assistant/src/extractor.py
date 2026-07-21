from dataclasses import dataclass
@dataclass(frozen=True)
class Action:text:str;owner:str|None=None
def extract(text:str)->list[Action]:
 return [Action(line.split(':',1)[1].strip()) for line in text.splitlines() if line.strip().lower().startswith('action:') and line.split(':',1)[1].strip()]
