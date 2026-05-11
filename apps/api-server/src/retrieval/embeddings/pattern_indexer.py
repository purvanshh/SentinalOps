from retrieval.embeddings.pattern_searcher import PatternSearcher
from retrieval.retrieval_orchestrator import RetrievalOrchestrator


def load_patterns() -> list[dict]:
    return PatternSearcher().patterns


def index_patterns() -> bool:
    orchestrator = RetrievalOrchestrator()
    patterns = orchestrator.load_pattern_file()
    if not patterns:
        return False
    return orchestrator.index_patterns(patterns)
