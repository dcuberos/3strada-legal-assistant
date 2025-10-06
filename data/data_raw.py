from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

url = "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2013-116041830"

# Configurar Chrome em modo headless
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

driver = webdriver.Chrome(options=options)

try:
    print("A aceder ao site...")
    driver.get(url)

    # Esperar o conteúdo carregar (aumentar tempo se necessário)
    print("A aguardar o carregamento do conteúdo...")
    time.sleep(5)  # Dar tempo para o JavaScript executar

    # Tentar esperar por elementos específicos (ajuste conforme a estrutura do site)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "content"))
        )
    except:
        print("Aviso: Timeout ao esperar por elementos específicos, continuando...")

    # Extrair todo o texto da página
    conteudo = driver.find_element(By.TAG_NAME, "body").text

    if len(conteudo) > 100:  # Verificar se há conteúdo real
        with open("codigo_estrada.txt", "w", encoding="utf-8") as f:
            f.write(conteudo)
        print(f"✓ Texto guardado com sucesso! ({len(conteudo)} caracteres)")
        print(f"Primeiras linhas:\n{conteudo[:500]}...")
    else:
        print(f"✗ Pouco conteúdo encontrado ({len(conteudo)} caracteres)")
        print(f"Conteúdo: {conteudo}")

        # Guardar HTML para debug
        with open("debug_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("HTML completo guardado em debug_page_source.html")

except Exception as e:
    print(f"Erro: {e}")

finally:
    driver.quit()