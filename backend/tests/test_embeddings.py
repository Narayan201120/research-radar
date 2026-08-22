from app.services.embeddings import (
    EMBEDDING_DIM,
    EmbeddingProvider,
    FastEmbedProvider,
    HashingFakeProvider,
)


def test_hashing_provider_is_deterministic():
    first = HashingFakeProvider().embed_texts(["attention is all you need"])[0]
    second = HashingFakeProvider().embed_texts(["attention is all you need"])[0]
    assert first == second


def test_hashing_provider_distinguishes_texts():
    provider = HashingFakeProvider()
    attention = provider.embed_texts(["attention mechanism"])[0]
    convolution = provider.embed_texts(["convolutional networks"])[0]
    assert attention != convolution


def test_hashing_provider_dimensions_and_batch_order():
    vectors = HashingFakeProvider().embed_texts(["one", "two", "three"])
    assert len(vectors) == 3
    assert all(len(vector) == EMBEDDING_DIM for vector in vectors)


def test_providers_satisfy_protocol():
    assert isinstance(HashingFakeProvider(), EmbeddingProvider)
    assert isinstance(FastEmbedProvider(model_name="unused"), EmbeddingProvider)


def test_fast_embed_empty_batch_avoids_model_load():
    provider = FastEmbedProvider(model_name="unused")

    def _boom():
        raise AssertionError("model must not load for an empty batch")

    provider._ensure_model = _boom
    assert provider.embed_texts([]) == []
