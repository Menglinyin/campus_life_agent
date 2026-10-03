from pathlib import Path
SKILLS={"classrooms":"classroom-search","dishes":"food-recommendation","courses":"course-auditing","secondhand":"secondhand-guidance"}
def registry(root):
    return {name:Path(root)/slug/"SKILL.md" for name,slug in SKILLS.items()}
