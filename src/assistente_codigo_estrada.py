import requests
import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

print("Carregando Codigo da Estrada...")

# Carregar JSON
with open(os.path.join(DATA_DIR, "codigo_estrada.json"), "r", encoding="utf-8") as f:
    artigos = json.load(f)

print(f"Carregados {len(artigos)} artigos")

# Criar textos para pesquisa
textos_completos = [
    f"{art['titulo']}\n{art['conteudo']}"
    for art in artigos
]

# Criar índice
print("Criando indice de pesquisa...")
vectorizer = TfidfVectorizer(max_features=500)
artigo_vectors = vectorizer.fit_transform(textos_completos)
print("Indice criado!")


def encontrar_artigos_relevantes(pergunta, top_k=2):
    """Encontra os artigos mais relevantes"""
    pergunta_vector = vectorizer.transform([pergunta])
    similaridades = cosine_similarity(pergunta_vector, artigo_vectors)[0]
    indices_relevantes = np.argsort(similaridades)[-top_k:][::-1]

    artigos_relevantes = []
    for idx in indices_relevantes:
        artigos_relevantes.append({
            'artigo': artigos[idx],
            'relevancia': similaridades[idx]
        })

    return artigos_relevantes


def perguntar_ollama(pergunta, modelo="phi3:mini"):
    """Pergunta ao Llama via Ollama"""

    print("\nProcurando artigos relevantes...")
    artigos_relevantes = encontrar_artigos_relevantes(pergunta, top_k=2)

    # Construir contexto
    contexto_parts = []
    for item in artigos_relevantes:
        art = item['artigo']
        contexto_parts.append(f"{art['titulo']}\n{art['conteudo']}")

    contexto = "\n\n---\n\n".join(contexto_parts)

    # Mostrar artigos encontrados
    print("Artigos encontrados:")
    for item in artigos_relevantes:
        print(f"  - {item['artigo']['titulo']} (relevancia: {item['relevancia']:.2f})")

    prompt = f"""Baseado nestes artigos do Codigo da Estrada portugues:

{contexto}

Pergunta: {pergunta}

Responde de forma breve e direta, citando o artigo quando relevante:"""

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
            timeout=60
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
    print("         ASSISTENTE DO CODIGO DA ESTRADA")
    print("=" * 70)
    print("\nModelos disponiveis:")
    print("  1. phi3:mini (3.8GB) - Recomendado")
    print("  2. llama3.2:1b (2GB) - Mais leve")

    escolha = input("\nEscolha o modelo (1-2) [1]: ").strip() or "1"

    modelos = {
        "1": "phi3:mini",
        "2": "llama3.2:1b"
    }

    modelo = modelos.get(escolha, "phi3:mini")
    print(f"\nUsando modelo: {modelo}")
    print("\nDigite 'sair' para terminar")
    print("Digite 'exemplos' para ver perguntas de exemplo\n")

    exemplos = [
        "Qual e o limite de velocidade em autoestrada?",
        "E obrigatorio usar cinto de seguranca?",
        "Posso usar telemovel ao conduzir?",
        "Qual a distancia minima para ultrapassar bicicletas?",
        "Criancas podem andar de bicicleta no passeio?"
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

        if not pergunta:
            continue

        resposta = perguntar_ollama(pergunta, modelo)
        print(f"\nResposta:\n{resposta}\n")
        print("-" * 70)


if __name__ == "__main__":
    main()
