from finsight_common.embeddings import HashEmbeddingProvider


def _cos(x, y):
    return sum(i * j for i, j in zip(x, y, strict=False))


def test_dim_and_shape():
    emb = HashEmbeddingProvider(dim=64)
    vectors = emb.embed(["hello world", "foo"])
    assert len(vectors) == 2
    assert all(len(v) == 64 for v in vectors)


def test_deterministic():
    emb = HashEmbeddingProvider(dim=64)
    assert emb.embed(["swiggy order"]) == emb.embed(["swiggy order"])


def test_normalized():
    emb = HashEmbeddingProvider(dim=64)
    (vector,) = emb.embed(["netflix subscription monthly"])
    norm = sum(x * x for x in vector) ** 0.5
    assert abs(norm - 1.0) < 1e-9


def test_similar_text_is_more_similar():
    emb = HashEmbeddingProvider(dim=256)
    a, b, c = emb.embed(["swiggy food order", "swiggy food delivery", "salary credit acme"])
    assert _cos(a, b) > _cos(a, c)
