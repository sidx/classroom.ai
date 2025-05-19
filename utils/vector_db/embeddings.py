from openai import OpenAI
from utils.vector_db.exceptions import SearchError
from typing import List, Tuple
import tiktoken

class EmbeddingGenerator:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.token_limit = 8000

    def generate_embedding(self, text: str):
        try:
            response = self.client.embeddings.create(input=[text], model="text-embedding-ada-002")
            return response.data[0].embedding  # Access as an attribute, not as a dictionary
        except Exception as e:
            raise SearchError(f"Failed to generate embedding: {str(e)}")

    def count_tokens(self, text: str) -> int:
        """Counts the number of tokens in a given text using OpenAI's tokenizer."""
        encoding = tiktoken.get_encoding("cl100k_base")  # Tokenizer initialized here
        return len(encoding.encode(text))

    def chunk_text(self, text: str) -> List[str]:
        """
        Splits text into chunks ensuring each chunk stays within the token limit.
        - Uses OpenAI's tokenizer for accurate token calculation.
        - Breaks text dynamically to stay within **8000 tokens** per chunk.
        """
        encoding = tiktoken.get_encoding("cl100k_base")  # Tokenizer initialized here
        tokens = encoding.encode(text)  # Convert text to token IDs
        chunks = []
        start = 0

        while start < len(tokens):
            end = min(start + self.token_limit, len(tokens))
            chunk_text = encoding.decode(tokens[start:end])  # Convert back to text
            chunks.append(chunk_text)
            start = end

        return chunks

    async def process_xml_content(self, xml_content: str) -> List[Tuple[List[float], int, bool]]:
        """
        Processes XML content, ensuring it stays within the token limit before embedding.
        Returns:
        - A list of tuples (embedding, rank, is_chunked)
        """
        if self.count_tokens(xml_content) <= self.token_limit:
            embedding = self.generate_embedding(xml_content)
            return [(embedding, 1, False)]  # Single chunk, no splitting

        # If content exceeds limit, split into token-based chunks
        chunks = self.chunk_text(xml_content)
        embeddings = [(self.generate_embedding(chunk), i + 1, True) for i, chunk in enumerate(chunks)]
        return embeddings