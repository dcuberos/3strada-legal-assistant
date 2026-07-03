"""Configuração central do 3strada."""

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.1:8b"
KEEP_ALIVE = "10m"

# e5 exige prefixos assimétricos query/passage
EMBEDDING_MODEL = "intfloat/multilingual-e5-base"
EMBEDDING_PREFIXO_QUERY = "query: "
EMBEDDING_PREFIXO_DOC = "passage: "

TOP_K = 5
# Pesos calibrados com gold set de 20 perguntas (hit@1 0.85, hit@3 1.00, MRR 0.925)
RRF_PESO_VETORIAL = 2.0
RRF_PESO_BM25 = 1.0
