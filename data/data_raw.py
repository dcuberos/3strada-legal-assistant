from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import re
import json

url = "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2013-116041830"

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=options)


def limpar_texto(texto):
    """Remove marcações desnecessárias do texto"""
    # Remover [...]
    texto = re.sub(r'\[\.\.\.\]', '', texto)

    # Remover (Anterior n.º X)
    texto = re.sub(r'\(Anterior \d+\.º\)', '', texto)
    texto = re.sub(r'\(Anterior n\.º \d+\.\)', '', texto)

    # Remover (ver documento original)
    texto = re.sub(r'\(ver documento original\)', '', texto)

    # Remover "(Revogado.)"
    texto = re.sub(r'\(Revogado\.\)', '[REVOGADO]', texto)

    # Remover linhas inteiras que só têm "..." (números, alíneas, etc.)
    texto = re.sub(r'\n\d+ - \.\.\.\n', '\n', texto)
    texto = re.sub(r'\n\d+\.º \.\.\.\n', '\n', texto)
    texto = re.sub(r'\n[a-z]\) \.\.\.\n', '\n', texto)

    # NOVO: Remover alíneas isoladas com apenas "..."
    texto = re.sub(r'\b[a-z]\) \.\.\.\s*', '', texto)
    texto = re.sub(r'\n[a-z]\) \.\.\.$', '', texto, flags=re.MULTILINE)

    # NOVO: Remover números seguidos de "..."
    texto = re.sub(r'\b\d+\.º \.\.\.\s*', '', texto)
    texto = re.sub(r'\b\d+ - \.\.\.\s*', '', texto)

    # Remover múltiplos espaços
    texto = re.sub(r' +', ' ', texto)

    # Remover múltiplas linhas vazias
    texto = re.sub(r'\n\s*\n\s*\n+', '\n\n', texto)

    # Remover linhas que só contêm pontos
    texto = re.sub(r'\n\.+\n', '\n', texto)

    return texto.strip()


try:
    print("A extrair Codigo da Estrada...")
    driver.get(url)
    time.sleep(5)

    conteudo = driver.find_element(By.TAG_NAME, "body").text

    print("A estruturar em artigos...")

    # Dividir por artigos
    artigos = re.split(r'(Artigo \d+\.º(?:-[A-Z])?[^\n]*)', conteudo)

    artigos_estruturados = []

    for artigo in artigos_estruturados:
        # Limpeza adicional no conteúdo
        conteudo = artigo['conteudo']

        # Remover linhas que são só alíneas vazias consecutivas
        conteudo = re.sub(r'([a-z]\) \.\.\.\s*){2,}', '', conteudo)

        artigo['conteudo'] = conteudo.strip()

    for i in range(1, len(artigos), 2):
        if i + 1 < len(artigos):
            titulo = artigos[i].strip()
            conteudo_artigo = artigos[i + 1].strip()

            # Limpar conteúdo
            conteudo_artigo = limpar_texto(conteudo_artigo)

            # Só adicionar se tiver conteúdo real (não apenas números vazios)
            if conteudo_artigo and len(conteudo_artigo) > 10:
                artigos_estruturados.append({
                    'titulo': titulo,
                    'conteudo': conteudo_artigo
                })

    # Guardar em formato de texto legível como codigo_estrada.txt
    with open("codigo_estrada.txt", "w", encoding="utf-8") as f:
        for artigo in artigos_estruturados:
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"{artigo['titulo']}\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"{artigo['conteudo']}\n")

    # Guardar em JSON
    with open("codigo_estrada.json", "w", encoding="utf-8") as f:
        json.dump(artigos_estruturados, f, ensure_ascii=False, indent=2)

    print(f"{len(artigos_estruturados)} artigos extraidos e limpos!")
    print("Ficheiros criados:")
    print("   - codigo_estrada.txt")
    print("   - codigo_estrada.json")

    # Mostrar exemplo
    print("\nExemplo de artigo limpo:")
    print("=" * 70)
    print(artigos_estruturados[0]['titulo'])
    print("=" * 70)
    print(artigos_estruturados[0]['conteudo'][:300] + "...")

except Exception as e:
    print(f"Erro: {e}")

finally:
    driver.quit()