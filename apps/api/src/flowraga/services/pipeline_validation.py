from typing import Protocol


class NodeLike(Protocol):
    id: str
    type: str


class EdgeLike(Protocol):
    source: str
    target: str


STAGE = {
    "source": 0,
    "chunk": 1,
    "embed": 2,
    "retrieve": 3,
    "rerank": 4,
    "generate": 5,
    "evaluate": 6,
}
REQUIRED = {"source", "chunk", "embed", "retrieve", "generate"}


def validate_pipeline_graph(nodes: list[NodeLike], edges: list[EdgeLike]) -> None:
    node_by_id = {node.id: node for node in nodes}
    if len(node_by_id) != len(nodes):
        raise ValueError("Pipeline node IDs must be unique")
    types = [node.type for node in nodes]
    missing = REQUIRED - set(types)
    if missing:
        raise ValueError(f"Pipeline is missing required nodes: {', '.join(sorted(missing))}")
    if any(types.count(node_type) > 1 for node_type in STAGE):
        raise ValueError("Each pipeline stage can appear only once")
    adjacency = {node.id: [] for node in nodes}
    indegree = {node.id: 0 for node in nodes}
    seen_edges: set[tuple[str, str]] = set()
    for edge in edges:
        if edge.source not in node_by_id or edge.target not in node_by_id:
            raise ValueError("Pipeline edges must reference existing nodes")
        pair = (edge.source, edge.target)
        if pair in seen_edges:
            raise ValueError("Duplicate pipeline edge")
        seen_edges.add(pair)
        if STAGE[node_by_id[edge.source].type] >= STAGE[node_by_id[edge.target].type]:
            raise ValueError("Pipeline edges must move forward between stages")
        adjacency[edge.source].append(edge.target)
        indegree[edge.target] += 1
    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = []
    while queue:
        current = queue.pop()
        visited.append(current)
        for target in adjacency[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(visited) != len(nodes):
        raise ValueError("Pipeline graph must not contain cycles")
    source_id = next(node.id for node in nodes if node.type == "source")
    generation_id = next(node.id for node in nodes if node.type == "generate")
    reachable = {source_id}
    stack = [source_id]
    while stack:
        for target in adjacency[stack.pop()]:
            if target not in reachable:
                reachable.add(target)
                stack.append(target)
    if generation_id not in reachable:
        raise ValueError("Pipeline must connect source to generation")
