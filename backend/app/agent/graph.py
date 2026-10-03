from langgraph.graph import StateGraph,START,END
from .state import AgentState
from .nodes import Nodes
def build_graph(services):
    nodes=Nodes(services); g=StateGraph(AgentState)
    for name in ['prepare','plan','execute','respond']: g.add_node(name,getattr(nodes,name))
    g.add_edge(START,'prepare'); g.add_edge('prepare','plan')
    g.add_conditional_edges('plan',lambda s:'execute' if s.get('calls') else 'respond')
    g.add_conditional_edges('execute',lambda s:'plan' if services.settings.llm_base_url and not s.get('answer') and s['steps']<services.settings.max_tool_steps else 'respond')
    g.add_edge('respond',END)
    return g.compile()
