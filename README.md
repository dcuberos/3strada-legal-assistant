# 3strada - Assistente do Código da Estrada Português

Chatbot conversacional que responde a perguntas sobre o Código da Estrada português, usando recuperação híbrida (BM25 + ChromaDB) e um LLM local via Ollama.

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Interface | [Chainlit](https://chainlit.io) |
| LLM | [Ollama](https://ollama.com) - modelo `llama3.1:8b` |
| Embeddings | `intfloat/multilingual-e5-base` (SentenceTransformers) |
| Base vetorial | ChromaDB (persistente em `data/chroma_db/`) |
| Recuperação | Híbrida: BM25 + ChromaDB com Reciprocal Rank Fusion (RRF) |

## Pré-requisitos

- Python 3.10+
- [Ollama](https://ollama.com/download) instalado e a correr

```powershell
# Instalar o modelo LLM
ollama pull llama3.1:8b
```

## Instalação

```powershell
# Clonar o repositório
git clone https://github.com/Dacni/Projeto-Final-LCDA
cd Projeto-Final-LCDA

# Criar ambiente virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements.txt
```

## Execução

```powershell
# Na raiz do projeto
python src/run.py
```

Abre o browser em `http://localhost:8000`.

Na primeira execução, a base vetorial é criada automaticamente a partir de `data/codigo_estrada.json` (pode demorar 1-2 minutos).

## Estrutura do Projeto

```
Projeto-Final-LCDA/
├── data/
│   ├── codigo_estrada.json   # Artigos do Código da Estrada
│   ├── codigo_estrada.txt    # Texto fonte
│   └── chroma_db/            # Base vetorial (gerada automaticamente)
├── src/
│   ├── app.py                # Interface Chainlit
│   ├── run.py                # Ponto de entrada
│   ├── assistente_vetorial.py # Lógica RAG + Ollama
│   ├── hybrid_retrieval.py   # Recuperação híbrida BM25 + ChromaDB
│   └── data_raw.py           # Parsing do texto fonte
└── README.md
```

## Como funciona

1. A pergunta do utilizador é primeiro classificada como relevante para o Código da Estrada (via LLM).
2. Se relevante, a recuperação híbrida encontra os artigos mais pertinentes (BM25 para keywords exatas + ChromaDB para semântica, fundidos com RRF).
3. O LLM gera uma resposta fundamentada nos artigos recuperados.
4. Os artigos fonte são apresentados como painéis laterais clicáveis na interface.
