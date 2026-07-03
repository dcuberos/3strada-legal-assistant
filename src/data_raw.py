import re
import json
import os

URL = "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2013-116041830"

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

_RE_ARTIGO = re.compile(r'^Artigo (\d+)\.º(?:-([A-Z]))?\s*$')
_RE_HIERARQUIA = re.compile(r'^(Título|Capítulo|Secção|Subsecção) [IVXLC]+$')


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

    # Remover alíneas isoladas com apenas "..."
    texto = re.sub(r'\b[a-z]\) \.\.\.\s*', '', texto)
    texto = re.sub(r'\n[a-z]\) \.\.\.$', '', texto, flags=re.MULTILINE)

    # Remover números seguidos de "..."
    texto = re.sub(r'\b\d+\.º \.\.\.\s*', '', texto)
    texto = re.sub(r'\b\d+ - \.\.\.\s*', '', texto)

    # Remover metadados de alterações do DR ("Alterado pelo/a ..." e blocos "Notas")
    texto = re.sub(r'^Alterado pelo/a .*$', '', texto, flags=re.MULTILINE)
    texto = re.split(r'^Notas$', texto, flags=re.MULTILINE)[0]

    # Remover múltiplos espaços
    texto = re.sub(r' +', ' ', texto)

    # Remover múltiplas linhas vazias
    texto = re.sub(r'\n\s*\n\s*\n+', '\n\n', texto)

    # Remover linhas que só contêm pontos
    texto = re.sub(r'\n\.+\n', '\n', texto)

    return texto.strip()


def estruturar_artigos(texto):
    """
    Estrutura o texto legal (a partir de 'Título I') numa lista de artigos:
        {artigo_id, numero, sufixo, titulo, epigrafe, capitulo, seccao,
         revogado, conteudo}

    Os marcadores de hierarquia (Título/Capítulo/Secção) aparecem entre
    artigos como duas linhas: o marcador e o nome. São extraídos para os
    campos capitulo/seccao e removidos do conteúdo.
    """
    artigos = []
    atual = None          # linhas do artigo em curso
    cabecalho = None      # (numero, sufixo)
    capitulo = None
    seccao = None
    pendente = None       # marcador de hierarquia à espera da linha do nome

    def fechar():
        if cabecalho is None or not atual:
            return
        numero, sufixo = cabecalho
        corpo = limpar_texto('\n'.join(atual))
        linhas = corpo.split('\n', 1)
        epigrafe = linhas[0].strip()
        conteudo = linhas[1].strip() if len(linhas) > 1 else ''
        if not conteudo and not epigrafe:
            return
        titulo = f"Artigo {numero}.º" + (f"-{sufixo}" if sufixo else "")
        artigos.append({
            'artigo_id': f"art{numero}{sufixo or ''}",
            'numero': numero,
            'sufixo': sufixo or '',
            'titulo': f"{titulo} — {epigrafe}" if epigrafe else titulo,
            'epigrafe': epigrafe,
            'capitulo': capitulo,
            'seccao': seccao,
            'revogado': conteudo.strip() in ('', '[REVOGADO]'),
            'conteudo': conteudo,
        })

    for linha in texto.split('\n'):
        linha = linha.strip()

        if pendente is not None:
            # linha do nome do marcador de hierarquia anterior
            tipo = pendente
            if tipo == 'Título':
                capitulo = None
                seccao = None
            elif tipo == 'Capítulo':
                capitulo = linha
                seccao = None
            elif tipo == 'Secção':
                seccao = linha
            # Subsecção: granularidade abaixo de secção, não guardamos
            pendente = None
            continue

        m = _RE_HIERARQUIA.match(linha)
        if m:
            fechar()
            atual = None
            cabecalho = None
            pendente = m.group(1)
            continue

        m = _RE_ARTIGO.match(linha)
        if m:
            fechar()
            cabecalho = (int(m.group(1)), m.group(2))
            atual = []
            continue

        if linha == 'Alterações ao artigo':
            continue

        if atual is not None:
            atual.append(linha)

    fechar()
    return artigos


_TABELA_VELOCIDADES = (
    "\n\n"
    "| Tipo de via            | Aut. Ligeiro | Motociclo | Aut. Pesado Mercad. | Aut. Pesado Pass. | Veíc. c/ Reboque | Veíc. c/ Reboque (pesado) |\n"
    "|------------------------|:------------:|:---------:|:-------------------:|:-----------------:|:----------------:|:-------------------------:|\n"
    "| Dentro das localidades |   50 km/h    |  50 km/h  |       50 km/h       |      50 km/h      |     50 km/h      |          50 km/h          |\n"
    "| Fora das localidades   |   90 km/h    |  90 km/h  |       80 km/h       |      90 km/h      |     70 km/h      |          80 km/h          |\n"
    "| Autoestrada            |  120 km/h    | 120 km/h  |       90 km/h       |     100 km/h      |     90 km/h      |         100 km/h          |\n"
    "\n"
)
_MARCADOR = "as seguintes velocidades instantâneas (em quilómetros/hora):"


def inserir_tabela_velocidades(artigos):
    """O Artigo 27.º tem uma tabela de velocidades que o scraping perde."""
    for artigo in artigos:
        if artigo['numero'] == 27 and not artigo['sufixo'] and _MARCADOR in artigo['conteudo']:
            artigo['conteudo'] = artigo['conteudo'].replace(
                _MARCADOR, _MARCADOR + _TABELA_VELOCIDADES
            )
            break
    return artigos


def guardar(artigos):
    with open(os.path.join(DATA_DIR, "codigo_estrada.txt"), "w", encoding="utf-8") as f:
        for artigo in artigos:
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"{artigo['titulo']}\n")
            if artigo['capitulo']:
                f.write(f"[{artigo['capitulo']}" + (f" / {artigo['seccao']}" if artigo['seccao'] else "") + "]\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"{artigo['conteudo']}\n")

    with open(os.path.join(DATA_DIR, "codigo_estrada.json"), "w", encoding="utf-8") as f:
        json.dump(artigos, f, ensure_ascii=False, indent=2)


def extrair():
    """Extrai o texto integral do Código da Estrada do Diário da República."""
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    import time

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(URL)
        time.sleep(5)
        conteudo = driver.find_element(By.TAG_NAME, "body").text
    finally:
        driver.quit()

    match = re.search(r'Título I\b', conteudo)
    if match:
        conteudo = conteudo[match.start():]
        print("Encontrado 'Título I' - Preâmbulo removido!")
    else:
        print("AVISO: Não foi possível encontrar o início. Processando tudo.")

    return conteudo


def main():
    print("A extrair Código da Estrada...")
    texto = extrair()

    print("A estruturar em artigos...")
    artigos = estruturar_artigos(texto)
    artigos = inserir_tabela_velocidades(artigos)

    guardar(artigos)

    revogados = sum(a['revogado'] for a in artigos)
    print(f"{len(artigos)} artigos extraídos e limpos ({revogados} revogados)!")
    print("Ficheiros criados:")
    print("   - data/codigo_estrada.txt")
    print("   - data/codigo_estrada.json")


if __name__ == "__main__":
    main()
