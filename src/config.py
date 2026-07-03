"""Configuração central do 3strada."""

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.1:8b"
KEEP_ALIVE = "10m"

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

TOP_K = 5
RRF_PESO_VETORIAL = 1.0
RRF_PESO_BM25 = 2.0  # BM25 com peso 2x por ser mais preciso lexicalmente
