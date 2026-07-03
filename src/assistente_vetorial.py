import re
import time
import requests
import json
import os

import config

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# Preenchidos por init()
artigos = None
collection = None
retriever = None
_indice_por_id = None


def _chunk_conteudo(conteudo):
    """Divide o conteúdo por números (1 - ...) ou, na falta deles, por alíneas."""
    partes = [p.strip() for p in re.split(r'(?m)^(?=\d+ - )', conteudo) if p.strip()]
    if len(partes) <= 1:
        alineas = [p.strip() for p in re.split(r'(?m)^(?=[a-z]{1,2}\) )', conteudo) if p.strip()]
        if len(alineas) > 1:
            partes = alineas
    return partes or [conteudo]


def init():
    """Carrega artigos e índices (Chroma + BM25). Idempotente; a primeira
    chamada pode demorar (construção de embeddings se o índice não existir)."""
    global artigos, collection, retriever, _indice_por_id
    if retriever is not None:
        return

    import chromadb
    from chromadb.utils import embedding_functions
    from hybrid_retrieval import HybridRetriever

    print("Carregando Código da Estrada...")
    with open(os.path.join(DATA_DIR, "codigo_estrada.json"), "r", encoding="utf-8") as f:
        artigos = json.load(f)
    _indice_por_id = {artigo['artigo_id']: i for i, artigo in enumerate(artigos)}
    print(f"Carregados {len(artigos)} artigos")

    print("Configurando base de dados vetorial...")
    client = chromadb.PersistentClient(path=os.path.join(DATA_DIR, "chroma_db"))

    # Modelo de embeddings multilingual (funciona bem em português)
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=config.EMBEDDING_MODEL
    )

    if "codigo_estrada" in [col.name for col in client.list_collections()]:
        print("Base vetorial já existe. Carregando...")
        collection = client.get_collection(
            name="codigo_estrada",
            embedding_function=embedding_function
        )
        print("Base vetorial carregada!")
    else:
        print("Criando nova base vetorial... (primeira vez pode demorar 1-2 minutos)")
        collection = client.create_collection(
            name="codigo_estrada",
            embedding_function=embedding_function
        )

        # Um documento por chunk (número/alínea), com o título do artigo como
        # contexto. O id "indice_chunk" permite reagrupar por artigo.
        ids = []
        documentos = []
        metadados = []
        for i, artigo in enumerate(artigos):
            if artigo['revogado']:
                continue
            for j, chunk in enumerate(_chunk_conteudo(artigo['conteudo'])):
                ids.append(f"{i}_{j}")
                documentos.append(f"{artigo['titulo']}\n{chunk}")
                metadados.append({
                    "artigo_id": artigo['artigo_id'],
                    "indice": i
                })

        collection.add(ids=ids, documents=documentos, metadatas=metadados)
        print(f"Base vetorial criada com {len(ids)} chunks de {len(artigos)} artigos!")

    retriever = HybridRetriever(collection, artigos, os.path.join(DATA_DIR, "bm25_index.pkl"))


def _lookup_por_numero(pergunta):
    match = re.search(r'artigo\s+(\d+)(?:\.º)?(?:-([A-Za-z]))?', pergunta, re.IGNORECASE)
    if not match:
        return None
    numero = int(match.group(1))
    sufixo = (match.group(2) or '').upper()
    for artigo in artigos:
        if artigo['numero'] == numero and artigo['sufixo'] == sufixo:
            return [{"artigo": artigo, "relevancia": 1.0, "distancia": None}]
    return None


def _enriquecer_com_regras_gerais(artigos_relevantes):
    """Quando um artigo de Exceções é recuperado, inclui o artigo anterior (regra geral)."""
    presentes = {item['artigo']['artigo_id'] for item in artigos_relevantes}
    extras = []

    for item in artigos_relevantes:
        if item['artigo']['epigrafe'].lower().startswith('exce'):
            i = _indice_por_id[item['artigo']['artigo_id']]
            if i > 0:
                anterior = artigos[i - 1]
                if anterior['artigo_id'] not in presentes:
                    extras.append({
                        'artigo': anterior,
                        'relevancia': item['relevancia'] + 0.001,
                        'distancia': None
                    })
                    presentes.add(anterior['artigo_id'])

    return extras + artigos_relevantes


def encontrar_artigos_relevantes(pergunta, top_k=3):
    """Encontra os artigos mais relevantes usando apenas busca vetorial"""
    init()
    resultados = collection.query(query_texts=[pergunta], n_results=top_k)

    artigos_relevantes = []
    for i in range(len(resultados['ids'][0])):
        indice = resultados['metadatas'][0][i]['indice']
        distancia = resultados['distances'][0][i]
        artigos_relevantes.append({
            'artigo': artigos[indice],
            'relevancia': 1 / (1 + distancia),
            'distancia': distancia
        })

    return artigos_relevantes


def e_pergunta_relevante(pergunta, modelo=config.MODELO):
    """Verifica se a mensagem está relacionada com o Código da Estrada."""
    # Few-shot para o modelo classificar a mensagem em vez de lhe responder
    # (ex.: "Posso usar o telemóvel enquanto conduzo?" → respondia "não" à pergunta)
    prompt = f"""A tua tarefa é classificar mensagens. NÃO respondas à mensagem.
Diz apenas "sim" se a mensagem estiver relacionada com o Código da Estrada português, regras de trânsito, condução, veículos ou infrações, e "não" caso contrário.

Mensagem: "Posso utilizar o telemóvel enquanto conduzo?"
Classificação: sim

Mensagem: "receita de bolo de chocolate"
Classificação: não

Mensagem: "quanto é a multa por estacionar no passeio?"
Classificação: sim

Mensagem: "{pergunta}"
Classificação:"""

    try:
        response = requests.post(
            config.OLLAMA_URL,
            json={
                "model": modelo,
                "prompt": prompt,
                "stream": False,
                "keep_alive": config.KEEP_ALIVE,
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
    init()

    direto = _lookup_por_numero(pergunta)
    if direto:
        print(f"\nReferência directa detectada → {direto[0]['artigo']['titulo']}")
        return direto

    print("\nProcurando artigos relevantes (busca híbrida BM25 + vetorial)...")
    artigos_relevantes = retriever.retrieve(pergunta, k=config.TOP_K)
    artigos_relevantes = _enriquecer_com_regras_gerais(artigos_relevantes)

    print("Artigos encontrados:")
    for item in artigos_relevantes:
        dist = item['distancia']
        dist_str = f"{dist:.2f}" if dist is not None else "n/a"
        print(f"  - {item['artigo']['titulo']} (rrf: {item['relevancia']:.4f}, dist: {dist_str})")

    return artigos_relevantes


def stream_resposta(pergunta, artigos_relevantes, modelo=config.MODELO):
    """Gera a resposta token a token (generator) via Ollama com stream=True."""

    contexto = "\n\n---\n\n".join(
        f"{item['artigo']['titulo']}\n{item['artigo']['conteudo']}"
        for item in artigos_relevantes
    )

    prompt = f"""Tu és um assistente especializado no Código da Estrada português.

CONTEXTO (artigos relevantes do Código da Estrada):

{contexto}

INSTRUÇÕES:
1. Responde APENAS com base no contexto fornecido acima.
2. Se a informação não estiver no contexto, diz apenas "Não tenho informação suficiente para responder a essa pergunta."
3. Cita sempre o artigo específico (exemplo: "Segundo o Artigo 27.º...").
4. Responde de forma breve e direta em português.
5. REGRA GERAL vs EXCEÇÕES: Se o contexto contiver um artigo de "Regra geral" e um de "Exceções", responde primeiro com a regra geral e só depois menciona as exceções. NUNCA apresentes uma exceção como se fosse a regra geral.
6. Quando o título de um artigo contiver "Exceções", isso significa que existem casos específicos em que a regra geral não se aplica — esses casos são exceções, não a norma.
7. NUNCA menciones o "contexto", os "artigos fornecidos", artigos "não disponíveis" ou qualquer detalhe sobre o teu funcionamento interno. O utilizador não sabe que existe um contexto. Se não tens informação, limita-te a dizer que não tens informação suficiente.

PERGUNTA: {pergunta}

RESPOSTA:"""

    print(f"\nPerguntando ao {modelo}...")

    _t0 = time.perf_counter()

    try:
        response = requests.post(
            config.OLLAMA_URL,
            json={
                "model": modelo,
                "prompt": prompt,
                "stream": True,
                "keep_alive": config.KEEP_ALIVE,
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
        yield "ERRO: O Ollama não está a correr!\n\nSolução:\n1. Abre um terminal\n2. Executa: ollama serve\n3. Tenta novamente"
    except Exception as e:
        yield f"Erro: {str(e)}"


def perguntar_ollama(pergunta, modelo=config.MODELO):
    """Pergunta ao Llama via Ollama (versão não-streaming, usada pelo CLI)."""
    artigos_relevantes = obter_artigos(pergunta)
    resposta = "".join(stream_resposta(pergunta, artigos_relevantes, modelo))
    return resposta, artigos_relevantes


def main():
    init()

    print("\n" + "=" * 70)
    print("    ASSISTENTE DO CÓDIGO DA ESTRADA (Busca Vetorial)")
    print("=" * 70)

    print(f"\nUsando modelo: {config.MODELO}")
    print("Usando busca híbrida: BM25 + ChromaDB com RRF")
    print("\nDigite 'sair' para terminar")
    print("Digite 'exemplos' para ver perguntas de exemplo")
    print("Digite 'teste' para comparar busca vetorial\n")

    exemplos = [
        "Qual é o limite de velocidade em autoestrada?",
        "É obrigatório usar cinto de segurança?",
        "Posso usar telemóvel ao conduzir?",
        "Qual a distância mínima para ultrapassar bicicletas?",
        "Crianças podem andar de bicicleta no passeio?",
        "quão rápido posso ir na via rápida?",
        "posso falar ao telefone enquanto conduzo?"
    ]

    while True:
        pergunta = input("\nPergunta: ").strip()

        if pergunta.lower() in ['sair', 'exit', 'quit']:
            print("\nAté logo!")
            break

        if pergunta.lower() == 'exemplos':
            print("\nExemplos de perguntas:")
            for i, ex in enumerate(exemplos, 1):
                print(f"  {i}. {ex}")
            continue

        if pergunta.lower() == 'teste':
            queries_teste = [
                "quão rápido posso andar?",
                "posso falar ao telemóvel?"
            ]
            for q in queries_teste:
                print(f"\n--- '{q}' ---")
                print("  [Vetorial]")
                for item in encontrar_artigos_relevantes(q, top_k=3):
                    print(f"    {item['artigo']['titulo']} (rel: {item['relevancia']:.3f})")
                print("  [Híbrido BM25+Vetorial RRF]")
                for item in retriever.retrieve(q, k=3):
                    dist_str = f"{item['distancia']:.3f}" if item['distancia'] is not None else "n/a"
                    print(f"    {item['artigo']['titulo']} (rrf: {item['relevancia']:.4f}, dist: {dist_str})")
            continue

        if not pergunta:
            continue

        resposta, _ = perguntar_ollama(pergunta, config.MODELO)
        print(f"\nResposta:\n{resposta}\n")
        print("-" * 70)


if __name__ == "__main__":
    main()
