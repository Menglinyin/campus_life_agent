from typing import TypedDict
class AgentState(TypedDict,total=False):
    user: str
    text: str
    history: list
    slots: dict
    preferences: dict
    messages: list
    results: list
    calls: list
    answer: str
    steps: int
    skills: str
