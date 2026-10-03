from .registry import registry
class SkillLoader:
    def __init__(self,root): self.paths=registry(root)
    def load(self,kinds):
        return "\n".join(self.paths[k].read_text(encoding="utf-8")[:6000] for k in kinds if k in self.paths and self.paths[k].is_file())
