import requests
import json
import chromadb
import os
from chromadb.utils import embedding_functions
from hybrid_retrieval import HybridRetriever

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

print("Carregando Codigo da Estrada...")

# Carregar JSON
with open(os.path.join(DATA_DIR, "codigo_estrada.json"), "r", encoding="utf-8") as f:
    artigos = json.load(f)

print(f"Carregados {len(artigos)} artigos")

# Configurar ChromaDB
print("Configurando base de dados vetorial...")

# Criar cliente ChromaDB (guarda na pasta data/chroma_db)
client = chromadb.PersistentClient(path=os.path.join(DATA_DIR, "chroma_db"))

# Usar modelo de embeddings multilingual (funciona bem em português)
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)

# Verificar se coleção já existe
colecoes_existentes = [col.name for col in client.list_collections()]

if "codigo_estrada" in colecoes_existentes:
    print("Base vetorial ja existe. Carregando...")
    collection = client.get_collection(
        name="codigo_estrada",
        embedding_function=embedding_function
    )
    print("Base vetorial carregada!")
else:
    print("Criando nova base vetorial...")
    print("(Primeira vez pode demorar 1-2 minutos)")

    collection = client.create_collection(
        name="codigo_estrada",
        embedding_function=embedding_function
    )

    print("Adicionando artigos a base vetorial...")

    # Preparar dados
    ids = []
    documentos = []
    metadados = []

    for i, artigo in enumerate(artigos):
        ids.append(f"artigo_{i}")
        documentos.append(f"{artigo['titulo']}\n{artigo['conteudo']}")
        metadados.append({
            "titulo": artigo['titulo'],
            "indice": i
        })

    # Adicionar em batch (mais rápido)
    collection.add(
        ids=ids,
        documents=documentos,
        metadatas=metadados
    )

    print(f"Base vetorial criada com {len(artigos)} artigos!")


# Inicializar retriever híbrido (BM25 + ChromaDB com RRF)
_bm25_index_path = os.path.join(DATA_DIR, "bm25_index.pkl")
retriever = HybridRetriever(collection, artigos, _bm25_index_path)


def encontrar_artigos_relevantes(pergunta, top_k=3):
    """Encontra os artigos mais relevantes usando busca vetorial"""

    # Buscar na base vetorial
    resultados = collection.query(
        query_texts=[pergunta],
        n_results=top_k
    )

    artigos_relevantes = []

    # Processar resultados
    for i in range(len(resultados['ids'][0])):
        indice = resultados['metadatas'][0][i]['indice']
        distancia = resultados['distances'][0][i]

        # Converter distância em relevância (0-1)
        relevancia = 1 / (1 + distancia)

        artigos_relevantes.append({
            'artigo': artigos[indice],
            'relevancia': relevancia,
            'distancia': distancia
        })

    return artigos_relevantes


def perguntar_ollama(pergunta, modelo="llama3.1:8b"):
    """Pergunta ao Llama via Ollama"""

    print("\nProcurando artigos relevantes (busca hibrida BM25 + vetorial)...")
    artigos_relevantes = retriever.retrieve(pergunta, k=3)

    # Construir contexto
    contexto_parts = []
    for item in artigos_relevantes:
        art = item['artigo']
        contexto_parts.append(f"{art['titulo']}\n{art['conteudo']}")

    contexto = "\n\n---\n\n".join(contexto_parts)

    # Mostrar artigos encontrados
    print("Artigos encontrados:")
    for item in artigos_relevantes:
        dist = item['distancia']
        dist_str = f"{dist:.2f}" if dist is not None else "n/a"
        print(f"  - {item['artigo']['titulo']} (rrf: {item['relevancia']:.4f}, dist: {dist_str})")

    prompt = f"""Tu es um assistente especializado no Codigo da Estrada portugues.

CONTEXTO (artigos relevantes do Codigo da Estrada):

{contexto}

INSTRUCOES:
1. Responde APENAS com base no contexto fornecido acima
2. Se a informacao nao estiver no contexto, diz "Nao encontrei essa informacao nos artigos fornecidos"
3. Cita sempre o artigo especifico (exemplo: "Segundo o Artigo 27.º...")
4. Responde de forma breve e direta em portugues

PERGUNTA: {pergunta}

RESPOSTA:"""

    print(f"\nPerguntando ao {modelo}...")

    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": modelo,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_ctx": 2048,
                    "num_predict": 250
                }
            },
            timeout=240
        )

        if response.status_code == 200:
            return response.json()['response']
        else:
            return f"Erro: {response.status_code}"

    except requests.exceptions.ConnectionError:
        return "ERRO: Ollama nao esta a correr!\n\nSolucao:\n1. Abra um terminal\n2. Execute: ollama serve\n3. Tente novamente"
    except Exception as e:
        return f"Erro: {str(e)}"


def main():
    print("\n" + "=" * 70)
    print("    ASSISTENTE DO CODIGO DA ESTRADA (Busca Vetorial)")
    print("=" * 70)

    modelo = "llama3.1:8b"
    print(f"\nUsando modelo: {modelo}")
    print("Usando busca hibrida: BM25 + ChromaDB com RRF")
    print("\nDigite 'sair' para terminar")
    print("Digite 'exemplos' para ver perguntas de exemplo")
    print("Digite 'teste' para comparar busca vetorial\n")

    exemplos = [
        "Qual e o limite de velocidade em autoestrada?",
        "E obrigatorio usar cinto de seguranca?",
        "Posso usar telemovel ao conduzir?",
        "Qual a distancia minima para ultrapassar bicicletas?",
        "Criancas podem andar de bicicleta no passeio?",
        "quao rapido posso ir na via rapida?",
        "posso falar ao telefone enquanto conduzo?"
    ]

    while True:
        pergunta = input("\nPergunta: ").strip()

        if pergunta.lower() in ['sair', 'exit', 'quit']:
            print("\nAte logo!")
            break

        if pergunta.lower() == 'exemplos':
            print("\nExemplos de perguntas:")
            for i, ex in enumerate(exemplos, 1):
                print(f"  {i}. {ex}")
            continue

        if pergunta.lower() == 'teste':
            queries_teste = [
                "quao rapido posso andar?",
                "posso falar ao telemovel?"
            ]
            for q in queries_teste:
                print(f"\n--- '{q}' ---")
                print("  [Vetorial]")
                for item in encontrar_artigos_relevantes(q, top_k=3):
                    print(f"    {item['artigo']['titulo']} (rel: {item['relevancia']:.3f})")
                print("  [Hibrido BM25+Vetorial RRF]")
                for item in retriever.retrieve(q, k=3):
                    dist_str = f"{item['distancia']:.3f}" if item['distancia'] is not None else "n/a"
                    print(f"    {item['artigo']['titulo']} (rrf: {item['relevancia']:.4f}, dist: {dist_str})")
            continue

        if not pergunta:
            continue

        resposta = perguntar_ollama(pergunta, modelo)
        print(f"\nResposta:\n{resposta}\n")
        print("-" * 70)


if __name__ == "__main__":
    main()
