from retrieval.embeddings.pattern_searcher import PatternSearcher


def load_patterns() -> list[dict]:
    return PatternSearcher().patterns
