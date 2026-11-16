import json
import os
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple
import boto3
from dotenv import load_dotenv

load_dotenv()

class RunbookRetriever:
    def __init__(self, runbooks_dir: Path, model_id: str = None, region_name: str = None):
        self.runbooks_dir = Path(runbooks_dir)
        self.region_name = region_name or os.getenv("AWS_REGION_NAME", "us-east-1")
        self.model_id = model_id or os.getenv("TITAN_MODEL_ID", "amazon.titan-embed-text-v2:0")
        
        self.bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.region_name,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        
        # In-memory index: list of dicts with {id, filename, content, embedding}
        self.indexed_runbooks: List[Dict[str, Any]] = []

    def get_embedding(self, text: str) -> List[float]:
        """Generates a normalized embedding vector using Bedrock Titan Embeddings V2."""
        body = json.dumps({
            "inputText": text,
            "dimensions": 512,
            "normalize": True
        })
        response = self.bedrock_runtime.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json"
        )
        response_body = json.loads(response["body"].read())
        return response_body.get("embedding", [])

    def index_runbooks(self) -> int:
        """Loads and embeds all markdown runbooks from the knowledge directory."""
        self.indexed_runbooks = []
        md_files = list(self.runbooks_dir.glob("*.md"))
        
        for file_path in md_files:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            embedding = self.get_embedding(content)
            self.indexed_runbooks.append({
                "filename": file_path.name,
                "path": str(file_path),
                "content": content,
                "embedding": embedding
            })
            
        return len(self.indexed_runbooks)

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates cosine similarity between two vectors (dot product if normalized)."""
        if not vec_a or not vec_b:
            return 0.0
        # If vectors are normalized, dot product equals cosine similarity
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 1, min_score: float = 0.5) -> List[Tuple[Dict[str, Any], float]]:
        """Finds the most relevant runbooks for a given query, filters out anything below min_score."""
        if not self.indexed_runbooks:
            self.index_runbooks()

        query_embedding = self.get_embedding(query)
        scored_runbooks = []

        for rb in self.indexed_runbooks:
            score = self.cosine_similarity(query_embedding, rb["embedding"])
            if score >= min_score:
                scored_runbooks.append((rb, score))

        # Sort descending by similarity score
        scored_runbooks.sort(key=lambda x: x[1], reverse=True)
        return scored_runbooks[:top_k]
