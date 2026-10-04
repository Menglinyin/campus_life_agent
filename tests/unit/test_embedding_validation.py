import numpy as np
import pytest
from app.rag.embedding_validation import validate_vectors, verify_lengths
from app.rag.embedding import Embedding
from app.settings import Settings

def test_fp16_input_checked_and_normalized_as_float32():
    result = validate_vectors(np.ones((2, 1024), dtype=np.float16), 2)
    assert result.dtype == np.float32 and result.shape == (2, 1024)
    np.testing.assert_allclose(np.linalg.norm(result, axis=1), 1, atol=1e-6)

@pytest.mark.parametrize('failure', ['dimension', 'count', 'nan', 'infinity', 'zero'])
def test_invalid_embeddings_rejected(failure):
    vectors = np.ones((1, 1024))
    if failure == 'dimension': vectors = np.ones((1, 768))
    elif failure == 'count': vectors = np.ones((2, 1024))
    elif failure == 'nan': vectors[0, 0] = np.nan
    elif failure == 'infinity': vectors[0, 0] = np.inf
    elif failure == 'zero': vectors[:] = 0
    with pytest.raises(ValueError): validate_vectors(vectors, 1)

def test_length_limit_includes_special_tokens_without_truncating():
    class Tokenizer:
        def encode(self, text, **kwargs):
            assert kwargs == {'add_special_tokens': True, 'truncation': False}
            return ['CLS', *text, 'SEP']
    assert verify_lengths(['abc'], Tokenizer(), 5) == [5]
    with pytest.raises(ValueError, match='rechunk'): verify_lengths(['abcd'], Tokenizer(), 5)

def test_demo_embedding_deterministic_and_empty_batch_has_known_dimension():
    embedding = Embedding(Settings(_env_file=None, embedding_backend='demo'))
    np.testing.assert_array_equal(embedding.encode(['校园助手']), embedding.encode(['校园助手']))
    assert embedding.encode([]).shape == (0, 1024)
    with pytest.raises(ValueError): embedding.encode([' '])
    with pytest.raises(ValueError): embedding.encode(['字' * 1024])
