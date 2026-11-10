from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    text: str
    steps: list[str]

def parse_node(state: State):
    return {"steps": state.get("steps", []) + ["parse"]}

def recommend_node(state: State):
    return {"steps": state.get("steps", []) + ["recommend"]}

def validate_node(state: State):
    return {"steps": state.get("steps", []) + ["validate"]}

graph = StateGraph(State)

graph.add_node("parse", parse_node)
graph.add_node("recommend", recommend_node)
graph.add_node("validate", validate_node)

graph.add_edge(START, "parse")
graph.add_edge("parse", "recommend")
graph.add_edge("recommend", "validate")
graph.add_edge("validate", END)

application = graph.compile()

result = application.invoke({
    "text": "фантастика без ужасов",
    "steps": [],
})

print(result)
