from finsight_common.vectorstore import InMemoryVectorStore, VectorRecord


def test_upsert_and_query_orders_by_similarity():
    store = InMemoryVectorStore()
    store.upsert(
        [
            VectorRecord("a", [1.0, 0.0], {"k": "a"}),
            VectorRecord("b", [0.0, 1.0], {"k": "b"}),
            VectorRecord("c", [0.9, 0.1], {"k": "c"}),
        ]
    )
    matches = store.query([1.0, 0.0], top_k=2)
    assert [m.id for m in matches] == ["a", "c"]
    assert matches[0].score >= matches[1].score


def test_upsert_replaces_same_id():
    store = InMemoryVectorStore()
    store.upsert([VectorRecord("a", [1.0, 0.0], {"v": 1})])
    store.upsert([VectorRecord("a", [1.0, 0.0], {"v": 2})])
    assert len(store) == 1
    assert store.query([1.0, 0.0])[0].metadata["v"] == 2


def test_zero_vector_scores_zero():
    store = InMemoryVectorStore()
    store.upsert([VectorRecord("a", [0.0, 0.0], {})])
    assert store.query([1.0, 0.0])[0].score == 0.0
