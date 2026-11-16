import json
import os
import re
import math
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Tuple
import boto3
from dotenv import load_dotenv

load_dotenv()

class RunbookRetriever:
    def __init__(self, runbooks_dir: Path, model_id: str = None, region_name: str = None):
        self.runbooks_dir = Path(runbooks_dir)
        self.cache_file = self.runbooks_dir.parent / ".embeddings_cache.json"
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

    @staticmethod
    def compute_semantic_hash(text: str) -> str:
        """
        Normalizes text before hashing so formatting noise (commas, periods,
        extra spaces, newline alignment) does NOT invalidate the cache.
        Only genuine word/content edits change the hash.
        """
        # Strip punctuation and symbols
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        # Collapse multiple spaces, tabs, and newlines into a single space
        normalized = " ".join(cleaned.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

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

    def _load_cache(self) -> Dict[str, Any]:
        """Loads cached embeddings from disk if available."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self, cache: Dict[str, Any]) -> None:
        """Persists embedding cache to disk."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save embeddings cache: {e}")

    def index_runbooks(self) -> int:
        """
        Loads runbooks using a smart content-hash cache. If a runbook has not changed meaningfully, its cached vector is reused. If words/content change, only that specific runbook is re-embedded.
        """
        self.indexed_runbooks = []
        cache = self._load_cache()
        updated_cache = {}
        
        md_files = sorted(list(self.runbooks_dir.glob("*.md")))
        reused_count = 0
        embedded_count = 0

        for file_path in md_files:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            content_hash = self.compute_semantic_hash(content)
            cached_entry = cache.get(file_path.name)

            if cached_entry and cached_entry.get("hash") == content_hash:
                embedding = cached_entry["embedding"]
                reused_count += 1
            else:
                embedding = self.get_embedding(content)
                embedded_count += 1

            updated_cache[file_path.name] = {
                "hash": content_hash,
                "embedding": embedding
            }

            self.indexed_runbooks.append({
                "filename": file_path.name,
                "path": str(file_path),
                "content": content,
                "embedding": embedding
            })

        self._save_cache(updated_cache)
        print(f"Index status: {reused_count} cached, {embedded_count} newly embedded via Titan.")
        return len(self.indexed_runbooks)

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates cosine similarity between two vectors."""
        if not vec_a or not vec_b:
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 1, min_score: float = 0.5) -> List[Tuple[Dict[str, Any], float]]:
        """Finds the most relevant runbooks for a given query, filtering out anything below min_score."""
        if not self.indexed_runbooks:
            self.index_runbooks()

        query_embedding = self.get_embedding(query)
        scored_runbooks = []

        for rb in self.indexed_runbooks:
            score = self.cosine_similarity(query_embedding, rb["embedding"])
            if score >= min_score:
                scored_runbooks.append((rb, score))

        scored_runbooks.sort(key=lambda x: x[1], reverse=True)
        return scored_runbooks[:top_k]
