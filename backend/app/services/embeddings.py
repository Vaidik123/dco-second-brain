import voyageai
from app.config import settings

_client = voyageai.Client(api_key=settings.voyage_api_key)

CHUNK_SIZE = 400  # words per chunk
CHUNK_OVERLAP = 50


def chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + CHUNK_SIZE])
        chunks.append(chunk)
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks if chunks else [text]


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed a batch of texts. input_type: 'document' for storage, 'query' for search."""
    result = _client.embed(texts, model="voyage-3", input_type=input_type)
    return result.embeddings


def embed_query(query: str) -> list[float]:
    result = _client.embed([query], model="voyage-3", input_type="query")
    return result.embeddings[0]
