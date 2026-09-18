import re
from collections import Counter


def token_f1(predicted: str, expected: str | None) -> float | None:
    if not expected:
        return None
    predicted_tokens = re.findall(r"\w+", predicted.lower())
    expected_tokens = re.findall(r"\w+", expected.lower())
    if not predicted_tokens or not expected_tokens:
        return 0.0
    overlap = sum((Counter(predicted_tokens) & Counter(expected_tokens)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(predicted_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall)


def retrieval_metrics(retrieved: list[str], expected: list[str]) -> dict[str, float | None]:
    retrieved_set, expected_set = set(retrieved), set(expected)
    if not expected_set:
        return {"retrieval_recall": None, "retrieval_precision": None}
    relevant = len(retrieved_set & expected_set)
    return {
        "retrieval_recall": relevant / len(expected_set),
        "retrieval_precision": relevant / len(retrieved_set) if retrieved_set else 0.0,
    }


def citation_metrics(answer: str, source_count: int) -> dict[str, float]:
    citations = [int(value) for value in re.findall(r"\[S(\d+)\]", answer)]
    validity = (
        sum(1 <= value <= source_count for value in citations) / len(citations)
        if citations
        else 0.0
    )
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", answer) if part.strip()]
    cited = sum(bool(re.search(r"\[S\d+\]", sentence)) for sentence in sentences)
    return {
        "citation_validity": validity,
        "citation_coverage": cited / len(sentences) if sentences else 0.0,
        "groundedness": validity * (cited / len(sentences) if sentences else 0.0),
    }


def aggregate_metrics(metrics: list[dict]) -> dict:
    keys = {key for item in metrics for key in item}
    summary = {}
    for key in keys:
        values = [item[key] for item in metrics if item.get(key) is not None]
        summary[key] = round(sum(values) / len(values), 4) if values else None
    summary["case_count"] = len(metrics)
    return summary
