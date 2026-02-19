"""
Tests for core/ai/action_search.py — ActionSearchEngine hybrid search.
"""
import pytest
from core.ai.action_search import ActionSearchEngine, ActionSearchResult


class TestActionSearchEngine:

    @pytest.fixture
    def engine(self):
        engine = ActionSearchEngine()
        engine.register_keywords("checkin", ["入住", "check-in", "登记"],
                                 entity="StayRecord", description="办理入住")
        engine.register_keywords("checkout", ["退房", "check-out", "结账"],
                                 entity="StayRecord", description="办理退房")
        engine.register_keywords("create_task", ["任务", "清洁", "维修"],
                                 entity="Task", description="创建任务")
        engine.register_keywords("add_payment", ["付款", "支付", "收款"],
                                 entity="Bill", description="添加付款")
        return engine

    def test_keyword_search_exact_match(self, engine):
        results = engine.search("办理入住")
        assert len(results) > 0
        assert results[0].name == "checkin"
        assert results[0].source == "keyword"

    def test_keyword_search_no_match(self, engine):
        results = engine.search("天气怎么样")
        assert len(results) == 0

    def test_keyword_search_multiple_actions(self, engine):
        # "入住" only matches checkin
        results = engine.search("入住")
        assert any(r.name == "checkin" for r in results)

    def test_embedding_unavailable_graceful(self, engine):
        """No embedding service -> keyword-only, no error."""
        results = engine.search("入住退房")
        assert all(r.source == "keyword" for r in results)

    def test_hybrid_dedup(self, engine):
        """Results should be deduplicated."""
        results = engine.search("入住")
        names = [r.name for r in results]
        assert len(names) == len(set(names))

    def test_search_top_k(self, engine):
        results = engine.search("入住退房任务付款", top_k=2)
        assert len(results) <= 2

    def test_register_keywords(self, engine):
        engine.register_keywords("new_action", ["新操作"], entity="X", description="test")
        results = engine.search("新操作")
        assert any(r.name == "new_action" for r in results)

    def test_cosine_similarity(self):
        sim = ActionSearchEngine._cosine_similarity([1, 0], [1, 0])
        assert sim == pytest.approx(1.0)

        sim = ActionSearchEngine._cosine_similarity([1, 0], [0, 1])
        assert sim == pytest.approx(0.0)

        sim = ActionSearchEngine._cosine_similarity([], [])
        assert sim == 0.0

    def test_cosine_similarity_zero_vector(self):
        sim = ActionSearchEngine._cosine_similarity([0, 0], [1, 0])
        assert sim == 0.0

    def test_cosine_similarity_different_lengths(self):
        sim = ActionSearchEngine._cosine_similarity([1, 0], [1, 0, 0])
        assert sim == 0.0

    def test_embedding_fallback_with_mock(self, engine):
        """When keyword results < 2 and embeddings exist, use embedding fallback."""
        # Mock embeddings
        engine._embeddings = {
            "checkin": [1.0, 0.0, 0.0],
            "checkout": [0.9, 0.1, 0.0],
            "create_task": [0.0, 1.0, 0.0],
        }

        class FakeEmbedding:
            def embed_sync(self, text):
                return [0.95, 0.05, 0.0]  # Similar to checkin/checkout

        engine._embedding_service = FakeEmbedding()

        # Query with keyword that only matches 1 action
        results = engine.search("办理退房程序")  # "退房" matches checkout only
        # Should have checkout from keyword + maybe checkin from embedding
        assert any(r.name == "checkout" for r in results)

    def test_embedding_fallback_produces_embedding_source(self, engine):
        """Embedding results should have source='embedding'."""
        engine._embeddings = {
            "checkin": [1.0, 0.0, 0.0],
            "checkout": [0.9, 0.1, 0.0],
            "create_task": [0.0, 1.0, 0.0],
        }

        class FakeEmbedding:
            def embed_sync(self, text):
                return [0.95, 0.05, 0.0]

        engine._embedding_service = FakeEmbedding()

        # "退房" matches only checkout via keyword -> triggers embedding fallback
        results = engine.search("办理退房程序")
        embedding_results = [r for r in results if r.source == "embedding"]
        # Should have at least one embedding result (checkin is similar)
        assert len(embedding_results) > 0

    def test_embedding_search_low_similarity_filtered(self, engine):
        """Results with similarity < 0.3 should be filtered out."""
        engine._embeddings = {
            "checkin": [1.0, 0.0, 0.0],
            "create_task": [0.0, 0.0, 1.0],  # Very dissimilar
        }

        class FakeEmbedding:
            def embed_sync(self, text):
                return [0.99, 0.01, 0.0]  # Similar to checkin, not create_task

        engine._embedding_service = FakeEmbedding()

        # Use query that doesn't match any keyword to force pure embedding search
        engine_clean = ActionSearchEngine(embedding_service=FakeEmbedding())
        engine_clean.register_keywords("checkin", ["xyz123"], entity="StayRecord", description="办理入住")
        engine_clean.register_keywords("create_task", ["abc456"], entity="Task", description="创建任务")
        engine_clean._embeddings = {
            "checkin": [1.0, 0.0, 0.0],
            "create_task": [0.0, 0.0, 1.0],
        }

        results = engine_clean.search("some unrelated query")
        # create_task should be filtered due to low similarity
        task_results = [r for r in results if r.name == "create_task"]
        assert len(task_results) == 0

    def test_embedding_service_error_graceful(self, engine):
        """Embedding service errors should not crash search."""
        engine._embeddings = {"checkin": [1.0, 0.0]}

        class BrokenEmbedding:
            def embed_sync(self, text):
                raise RuntimeError("Embedding service down")

        engine._embedding_service = BrokenEmbedding()

        # Should fall back gracefully to keyword-only results
        results = engine.search("退房")
        # "退房" matches checkout via keyword
        assert any(r.name == "checkout" for r in results)

    def test_keyword_case_insensitive(self, engine):
        """Keywords should match case-insensitively."""
        engine.register_keywords("test_action", ["Check-In", "REGISTER"],
                                 entity="Test", description="test")
        results = engine.search("check-in")
        assert any(r.name == "test_action" for r in results)

    def test_multiple_keyword_match_higher_score(self, engine):
        """Actions matching more keywords should score higher."""
        results = engine.search("入住登记")  # Both "入住" and "登记" match checkin
        assert len(results) > 0
        assert results[0].name == "checkin"
        assert results[0].score >= 2.0

    def test_search_result_fields(self, engine):
        """Verify all fields are populated correctly."""
        results = engine.search("入住")
        assert len(results) > 0
        r = results[0]
        assert r.name == "checkin"
        assert r.entity == "StayRecord"
        assert r.description == "办理入住"
        assert r.score > 0
        assert r.source == "keyword"

    def test_keyword_no_duplicate_registration(self, engine):
        """Registering the same keyword twice should not create duplicate entries."""
        engine.register_keywords("checkin", ["入住"], entity="StayRecord", description="办理入住")
        # "入住" should still only map to checkin once
        assert engine._keyword_index["入住"].count("checkin") == 1

    def test_search_with_user_role(self, engine):
        """user_role parameter should not cause errors (future use)."""
        results = engine.search("入住", user_role="receptionist")
        assert len(results) > 0

    def test_empty_engine_search(self):
        """Search on empty engine should return empty results."""
        engine = ActionSearchEngine()
        results = engine.search("anything")
        assert results == []

    def test_keyword_search_returns_two_skips_embedding(self):
        """When keyword search returns >= 2 results, embedding is not used."""
        engine = ActionSearchEngine()
        engine.register_keywords("a1", ["test"], entity="X", description="d1")
        engine.register_keywords("a2", ["test"], entity="X", description="d2")

        # Even with embeddings present, should not use them
        engine._embeddings = {"a1": [1.0], "a2": [0.5]}

        class FakeEmbedding:
            def embed_sync(self, text):
                raise RuntimeError("Should not be called")

        engine._embedding_service = FakeEmbedding()

        results = engine.search("test")
        assert len(results) == 2
        assert all(r.source == "keyword" for r in results)
