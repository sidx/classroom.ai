from .base import VectorDBAdapter
from .elastic_adapter import ElasticSearchAdapter

class VectorDBContext:
    def __init__(self, adapter: VectorDBAdapter):
        self.adapter = adapter
    
    async def __aenter__(self) -> VectorDBAdapter:
        await self.adapter.connect()
        return self.adapter
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.adapter.close()

def create_vector_db() -> VectorDBAdapter:
    return ElasticSearchAdapter()
