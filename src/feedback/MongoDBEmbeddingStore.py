import os
from typing import List, Dict, Any, Optional, Union
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
import math

# Load environment variables
load_dotenv()


class MongoDBEmbeddingStore:
    """
    A class to store and manage embeddings in MongoDB.
    
    This class provides functionality to:
    - Generate embeddings from text using OpenAI embeddings
    - Store embeddings in MongoDB with metadata
    - Retrieve embeddings and perform similarity searches
    - Manage embedding collections
    """
    
    def __init__(
        self,
        mongodb_uri: Optional[str] = None,
        database_name: str = "test-saptarshi",
        collection_name: str = "feedback-vector",
        embedding_model: Optional[OpenAIEmbeddings] = None,
        dimension: int = 1536  # Default OpenAI embedding dimension
    ):
        """
        Initialize the MongoDB Embedding Store.
        
        Args:
            mongodb_uri: MongoDB connection URI. If None, uses MONGODB_URI from .env
            database_name: Name of the MongoDB database
            collection_name: Name of the collection to store embeddings
            embedding_model: OpenAIEmbeddings instance. If None, creates a new one
            dimension: Dimension of the embeddings (default 1536 for OpenAI)
        """
        self.mongodb_uri = mongodb_uri or os.getenv('MONGODB_URI')
        if not self.mongodb_uri:
            raise ValueError("MongoDB URI must be provided or set in .env file as MONGODB_URI")
        
        self.database_name = database_name
        self.collection_name = collection_name
        self.dimension = dimension
        
        # Initialize MongoDB client
        self.client = MongoClient(self.mongodb_uri)
        self.db: Database = self.client[self.database_name]
        self.collection: Collection = self.db[self.collection_name]
        
        # Initialize embedding model
        if embedding_model is None:
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY must be set in .env file")
            self.embedding_model = OpenAIEmbeddings(openai_api_key=openai_api_key)
        else:
            self.embedding_model = embedding_model
        
        # Create vector search index if it doesn't exist
        self._ensure_vector_index()
    
    def _ensure_vector_index(self):
        """
        Ensure a vector search index exists on the collection.
        This is required for vector similarity search in MongoDB Atlas.
        """
        try:
            # Check if index already exists
            indexes = self.collection.list_indexes()
            index_names = [idx['name'] for idx in indexes]
            
            if 'vector_index' not in index_names:
                # Create vector search index
                # Note: This requires MongoDB Atlas with vector search enabled
                # For local MongoDB, you may need to create the index differently
                try:
                    self.db.command({
                        "createSearchIndexes": self.collection_name,
                        "indexes": [
                            {
                                "name": "vector_index",
                                "definition": {
                                    "mappings": {
                                        "dynamic": True,
                                        "fields": {
                                            "embedding": {
                                                "type": "knnVector",
                                                "dimensions": self.dimension,
                                                "similarity": "cosine"
                                            }
                                        }
                                    }
                                }
                            }
                        ]
                    })
                    print(f"✓ Created vector search index 'vector_index' on collection '{self.collection_name}'")
                except Exception as e:
                    print(f"⚠ Warning: Could not create vector search index: {e}")
                    print("  This is normal for local MongoDB. Vector search requires MongoDB Atlas.")
        except Exception as e:
            print(f"⚠ Warning: Could not check/create vector index: {e}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding for a single text.
        
        Args:
            text: The text to generate an embedding for
            
        Returns:
            List of floats representing the embedding vector
        """
        return self.embedding_model.embed_query(text)
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to generate embeddings for
            
        Returns:
            List of embedding vectors
        """
        return self.embedding_model.embed_documents(texts)
    
    def add_embedding(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
        document_id: Optional[str] = None
    ) -> str:
        """
        Add a single embedding to MongoDB.
        
        Args:
            text: The text content
            metadata: Optional metadata dictionary to store with the embedding
            embedding: Pre-computed embedding. If None, will generate one
            document_id: Optional custom document ID. If None, MongoDB will generate one
            
        Returns:
            The inserted document ID
        """
        if embedding is None:
            embedding = self.generate_embedding(text)
        
        document = {
            "text": text,
            "embedding": embedding,
            "metadata": metadata or {},
        }
        
        if document_id:
            document["_id"] = document_id
        
        result = self.collection.insert_one(document)
        return str(result.inserted_id)
    
    def add_embeddings(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add multiple embeddings to MongoDB in batch.
        
        Args:
            texts: List of text contents
            metadatas: Optional list of metadata dictionaries
            embeddings: Optional pre-computed embeddings. If None, will generate them
            ids: Optional list of custom document IDs
            
        Returns:
            List of inserted document IDs
        """
        if embeddings is None:
            embeddings = self.generate_embeddings(texts)
        
        if metadatas is None:
            metadatas = [{}] * len(texts)
        
        if ids is None:
            ids = [None] * len(texts)
        
        documents = []
        for i, text in enumerate(texts):
            doc = {
                "text": text,
                "embedding": embeddings[i],
                "metadata": metadatas[i] if i < len(metadatas) else {},
            }
            if ids[i] is not None:
                doc["_id"] = ids[i]
            documents.append(doc)
        
        result = self.collection.insert_many(documents)
        return [str(id) for id in result.inserted_ids]
    
    def search(
        self,
        query_text: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar embeddings using vector similarity.
        
        Args:
            query_text: The query text to search for
            limit: Maximum number of results to return
            filter: Optional MongoDB filter for metadata
            query_embedding: Optional pre-computed query embedding
            
        Returns:
            List of matching documents with similarity scores
        """
        if query_embedding is None:
            query_embedding = self.generate_embedding(query_text)
        
        # Build the aggregation pipeline for vector search
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": limit * 10,  # Search more candidates for better results
                    "limit": limit
                }
            }
        ]
        
        # Add metadata filter if provided
        if filter:
            pipeline.append({"$match": filter})
        
        # Add score to results
        pipeline.append({
            "$addFields": {
                "score": {"$meta": "vectorSearchScore"}
            }
        })
        
        try:
            results = list(self.collection.aggregate(pipeline))
            return results
        except Exception as e:
            # Fallback to cosine similarity calculation if vector search is not available
            print(f"⚠ Vector search not available, using cosine similarity: {e}")
            return self._cosine_similarity_search(query_embedding, limit, filter)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have the same length")
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _cosine_similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fallback cosine similarity search when vector search index is not available.
        
        Args:
            query_embedding: The query embedding vector
            limit: Maximum number of results
            filter: Optional metadata filter
            
        Returns:
            List of matching documents with similarity scores
        """
        query = filter or {}
        documents = list(self.collection.find(query))
        
        # Calculate cosine similarity for each document
        results = []
        
        for doc in documents:
            if "embedding" in doc:
                similarity = self._cosine_similarity(query_embedding, doc["embedding"])
                doc["score"] = float(similarity)
                results.append(doc)
        
        # Sort by similarity score and return top results
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:limit]
    
    def close(self):
        """Close the MongoDB connection."""
        self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

