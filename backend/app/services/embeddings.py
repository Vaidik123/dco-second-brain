import time
import voyageai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
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


@retry(
    wait=wait_exponential(multiplier=2, min=20, max=120),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(Exception),
)
def _embed_with_retry(texts: list[str], input_type: str) -> list[list[float]]:
    """Embed with exponential backoff for rate limits (Voyage free tier: 3 RPM)."""
    result = _client.embed(texts, model="voyage-3", input_type=input_type)
    return result.embeddings


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed a batch of texts. input_type: 'document' for storage, 'query' for search.

    Splits into small batches to respect Voyage AI free tier rate limits (3 RPM, 10K TPM).
    Each batch gets 20s spacing to stay under limits.
    """
    if not texts:
        return []

    # Batch into groups of 4 chunks max to stay under TPM limits
    all_embeddings = []
    batch_size = 4
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = _embed_with_retry(batch, input_type)
        all_embeddings.extend(embeddings)
        # Throttle: 3 RPM = 1 request per 20s on free tier
        if i + batch_size < len(texts):
            time.sleep(20)

    return all_embeddings


def embed_query(query: str) -> list[float]:
    result = _embed_with_retry([query], "query")
    return result[0]
