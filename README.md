# 3strada - Portuguese Highway Code Assistant

Conversational chatbot that answers questions about the Portuguese Highway Code (Código da Estrada), using hybrid retrieval (BM25 + ChromaDB) and a local LLM via Ollama.

## Technologies

| Layer | Technology |
|---|---|
| Interface | [Chainlit](https://chainlit.io) |
| LLM | [Ollama](https://ollama.com) - `llama3.1:8b` model |
| Embeddings | `intfloat/multilingual-e5-base` (SentenceTransformers) |
| Vector store | ChromaDB (persistent in `data/chroma_db/`) |
| Retrieval | Hybrid: BM25 + ChromaDB with Reciprocal Rank Fusion (RRF) |

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running

```powershell
# Install the LLM model
ollama pull llama3.1:8b
```

## Installation

```powershell
# Clone the repository
git clone https://github.com/Dacni/Projeto-Final-LCDA
cd Projeto-Final-LCDA

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## Running the App

```powershell
# From the project root
python src/run.py
```

Open the browser at `http://localhost:8000`.

On the first run, the vector store is created automatically from `data/codigo_estrada.json` (this can take 1 to 2 minutes).

## Project Structure

```
Projeto-Final-LCDA/
├── data/
│   ├── codigo_estrada.json   # Highway Code articles
│   ├── codigo_estrada.txt    # Source text
│   └── chroma_db/            # Vector store (generated automatically)
├── src/
│   ├── app.py                # Chainlit interface
│   ├── run.py                # Entry point
│   ├── assistente_vetorial.py # RAG + Ollama logic
│   ├── hybrid_retrieval.py   # Hybrid BM25 + ChromaDB retrieval
│   └── data_raw.py           # Source text parsing
└── README.md
```

## How It Works

1. The user's question is first classified as relevant to the Highway Code (via LLM).
2. If relevant, hybrid retrieval finds the most pertinent articles (BM25 for exact keywords + ChromaDB for semantic matching, merged with RRF).
3. The LLM generates an answer grounded in the retrieved articles.
4. The source articles are shown as clickable side panels in the interface.
