import os
import chromadb
from sentence_transformers import SentenceTransformer

# Setup Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chroma_storage")

class VectorDB:
    def __init__(self, collection_name="rti_cases"):
        # Initialize the embedding model (downloads on first run)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize ChromaDB Persistent Client
        self.client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        
        # Get or create the collection
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self.embedding_model.encode(texts)
        return embeddings.tolist()

    def add_cases(self, cases: list[dict]):
        """
        Add RTI cases to the vector database.
        Expected format for each case:
        {
            "id": "case_1",
            "query": "What is the budget for road repair?",
            "metadata": {
                "decision": "accepted",
                "reason": "Public expenditure information",
                "date": "2023-10-12"
            }
        }
        """
        if not cases:
            return

        ids = [str(case["id"]) for case in cases]
        documents = [case["query"] for case in cases]
        metadatas = [case.get("metadata", {}) for case in cases]
        
        embeddings = self._get_embeddings(documents)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    def search_cases(self, query: str, top_k: int = 3) -> list[dict]:
        """Search for similar RTI queries and return context."""
        query_embedding = self._get_embeddings([query])

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )
        
        retrieved_cases = []
        if results['documents'] and len(results['documents']) > 0:
            for i in range(len(results['documents'][0])):
                retrieved_cases.append({
                    "id": results['ids'][0][i],
                    "query": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i] if 'distances' in results and results['distances'] else None
                })
                
        return retrieved_cases

# Singleton instance for easy import
db = VectorDB()
