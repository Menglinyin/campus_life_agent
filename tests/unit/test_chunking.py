import pytest
from app.rag.chunking import chunk_text

def test_overlap_preserves_boundary_content():
    assert chunk_text('abcdefgh', size=4, overlap=1) == ['abcd', 'defg', 'gh']

@pytest.mark.parametrize('size,overlap', [(4, 4), (4, -1), (0, 0)])
def test_invalid_window_rejected(size, overlap):
    with pytest.raises(ValueError): chunk_text('text', size, overlap)

def test_empty_and_whitespace_produce_no_chunks():
    assert chunk_text('') == []
    assert chunk_text('   \n\t') == []

def test_tokenizer_receives_no_truncation_and_unicode_is_preserved():
    class Tokenizer:
        def encode(self, text, **kwargs):
            assert kwargs == {'add_special_tokens': False, 'truncation': False}
            return list(text)
        def decode(self, tokens, **kwargs):
            assert kwargs == {'skip_special_tokens': True}
            return ''.join(tokens)
    assert chunk_text('校园生活助手', 3, 1, Tokenizer()) == ['校园生', '生活助', '助手']
