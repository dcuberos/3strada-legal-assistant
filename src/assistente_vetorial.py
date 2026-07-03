import re
import time
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


def _lookup_por_numero(pergunta):
    match = re.search(r'artigo\s+(\d+)(?:\.º)?(?:-([A-Z]))?', pergunta, re.IGNORECASE)
    if not match:
        return None
    numero = match.group(1)
    sufixo = match.group(2)
    titulo_alvo = f"Artigo {numero}.º" + (f"-{sufixo}" if sufixo else "")
    for artigo in artigos:
        if artigo["titulo"].startswith(titulo_alvo):
            return [{"artigo": artigo, "relevancia": 1.0, "distancia": None}]
    return None


def _enriquecer_com_regras_gerais(artigos_relevantes):
    """Quando um artigo de Exceções é recuperado, inclui o artigo anterior (regra geral)."""
    titulos_presentes = {item['artigo']['titulo'] for item in artigos_relevantes}
    extras = []

    for item in artigos_relevantes:
        conteudo_inicio = item['artigo']['conteudo'].strip().lower()[:20]
        if conteudo_inicio.startswith('exce'):
            titulo = item['artigo']['titulo']
            for i, art in enumerate(artigos):
                if art['titulo'] == titulo and i > 0:
                    anterior = artigos[i - 1]
                    if anterior['titulo'] not in titulos_presentes:
                        extras.append({
                            'artigo': anterior,
                            'relevancia': item['relevancia'] + 0.001,
                            'distancia': None
                        })
                        titulos_presentes.add(anterior['titulo'])
                    break

    return extras + artigos_relevantes


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


def e_pergunta_relevante(pergunta, modelo="llama3.1:8b"):
    """Verifica se a mensagem está relacionada com o Código da Estrada."""
    prompt = f"""Responde apenas com "sim" ou "não", sem mais texto.
A mensagem seguinte está relacionada com o Código da Estrada português, regras de trânsito, condução, veículos, infrações ou tópicos similares?

Mensagem: {pergunta}

Resposta:"""

    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": modelo,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.0,
                    "num_predict": 5,
                    "num_ctx": 512
                }
            },
            timeout=30
        )
        if response.status_code == 200:
            resposta = response.json()['response'].strip().lower()
            print(f"[Classificação] '{pergunta}' → {resposta!r}")
            return resposta.startswith("sim")
        return True  # em caso de erro, deixa passar
    except Exception as e:
        print(f"[Classificação] Erro: {e}")
        return True  # em caso de erro, deixa passar


def obter_artigos(pergunta):
    """Retrieval: lookup directo por número ou busca híbrida BM25 + vetorial."""
    direto = _lookup_por_numero(pergunta)
    if direto:
        print(f"\nReferência directa detectada → {direto[0]['artigo']['titulo']}")
        return direto

    print("\nProcurando artigos relevantes (busca hibrida BM25 + vetorial)...")
    artigos_relevantes = retriever.retrieve(pergunta, k=5)
    artigos_relevantes = _enriquecer_com_regras_gerais(artigos_relevantes)

    print("Artigos encontrados:")
    for item in artigos_relevantes:
        dist = item['distancia']
        dist_str = f"{dist:.2f}" if dist is not None else "n/a"
        print(f"  - {item['artigo']['titulo']} (rrf: {item['relevancia']:.4f}, dist: {dist_str})")

    return artigos_relevantes


def stream_resposta(pergunta, artigos_relevantes, modelo="llama3.1:8b"):
    """Gera a resposta token a token (generator) via Ollama com stream=True."""

    contexto = "\n\n---\n\n".join(
        f"{item['artigo']['titulo']}\n{item['artigo']['conteudo']}"
        for item in artigos_relevantes
    )

    prompt = f"""Tu es um assistente especializado no Codigo da Estrada portugues.

CONTEXTO (artigos relevantes do Codigo da Estrada):

{contexto}

INSTRUCOES:
1. Responde APENAS com base no contexto fornecido acima.
2. Se a informacao nao estiver no contexto, diz apenas "Nao tenho informacao suficiente para responder a essa pergunta."
3. Cita sempre o artigo especifico (exemplo: "Segundo o Artigo 27.º...").
4. Responde de forma breve e direta em portugues.
5. REGRA GERAL vs EXCECOES: Se o contexto contiver um artigo de "Regra geral" e um de "Excecoes", responde primeiro com a regra geral e so depois menciona as excecoes. NUNCA apresentes uma excecao como se fosse a regra geral.
6. Quando um artigo comecar por "Excecoes", isso significa que existem casos especificos em que a regra geral nao se aplica — esses casos sao excecoes, nao a norma.
7. NUNCA menciones o "contexto", os "artigos fornecidos", artigos "nao disponiveis" ou qualquer detalhe sobre o teu funcionamento interno. O utilizador nao sabe que existe um contexto. Se nao tens informacao, limita-te a dizer que nao tens informacao suficiente.

PERGUNTA: {pergunta}

RESPOSTA:"""

    print(f"\nPerguntando ao {modelo}...")

    _t0 = time.perf_counter()

    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": modelo,
                "prompt": prompt,
                "stream": True,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.2,
                    "num_ctx": 4096,
                    "num_predict": 512
                }
            },
            timeout=600,
            stream=True
        )

        if response.status_code != 200:
            try:
                detalhe = response.json().get('error', response.text)
            except Exception:
                detalhe = response.text
            yield f"Erro Ollama ({response.status_code}): {detalhe}"
            return

        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if chunk.get('response'):
                yield chunk['response']
            if chunk.get('done'):
                break

        _elapsed = time.perf_counter() - _t0
        print(f"[TEMPO] Ollama respondeu em {_elapsed:.1f}s")

    except requests.exceptions.ConnectionError:
        yield "ERRO: Ollama nao esta a correr!\n\nSolucao:\n1. Abra um terminal\n2. Execute: ollama serve\n3. Tente novamente"
    except Exception as e:
        yield f"Erro: {str(e)}"


def perguntar_ollama(pergunta, modelo="llama3.1:8b"):
    """Pergunta ao Llama via Ollama (versão não-streaming, usada pelo CLI)."""
    artigos_relevantes = obter_artigos(pergunta)
    resposta = "".join(stream_resposta(pergunta, artigos_relevantes, modelo))
    return resposta, artigos_relevantes


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

        resposta, _ = perguntar_ollama(pergunta, modelo)
        print(f"\nResposta:\n{resposta}\n")
        print("-" * 70)


if __name__ == "__main__":
    main()
