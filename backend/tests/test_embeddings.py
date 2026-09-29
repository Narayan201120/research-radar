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


class _RaggedStubModel:
    """Mimics fastembed's ragged-tokenizer failure: a multi-text batch with
    mixed lengths raises ValueError like the bare np.array in onnx_embed,
    while single texts always succeed."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed(self, texts):
        self.calls.append(list(texts))
        if len(texts) > 1 and len({len(text) for text in texts}) > 1:
            raise ValueError("setting an array element with a sequence")
        for text in texts:
            yield _LengthVector(len(text))


class _LengthVector:
    def __init__(self, seed: int):
        self._seed = seed

    def tolist(self):
        return [float(self._seed)] * EMBEDDING_DIM


def _stubbed_provider():
    provider = FastEmbedProvider(model_name="unused")
    stub = _RaggedStubModel()
    provider._model = stub
    return provider, stub


def test_fast_embed_splits_ragged_batch_preserving_order():
    provider, _stub = _stubbed_provider()
    vectors = provider.embed_texts(["a", "bb", "ccc"])
    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0]
    assert all(len(vector) == EMBEDDING_DIM for vector in vectors)


def test_fast_embed_uniform_batch_embeds_in_one_call():
    provider, stub = _stubbed_provider()
    vectors = provider.embed_texts(["aa", "bb", "cc"])
    assert len(vectors) == 3
    assert len(stub.calls) == 1


def test_fast_embed_single_failure_still_raises():
    provider, _stub = _stubbed_provider()

    class _AlwaysFails(_RaggedStubModel):
        def embed(self, texts):
            raise ValueError("onnx session failed")

    provider._model = _AlwaysFails()
    try:
        provider.embed_texts(["ok"])
    except ValueError:
        pass
    else:
        raise AssertionError("single-text failure must raise")
