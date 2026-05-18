import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

def embed(text: str) -> np.ndarray:
    return model.encode(text, normalize_embeddings=True)

def similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))