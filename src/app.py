import re
import sys
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import chainlit as cl
import assistente_vetorial as _av

_executor = ThreadPoolExecutor(max_workers=2)


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Limite de velocidade em autoestrada",
            message="Qual é o limite de velocidade em autoestrada?",
        ),
        cl.Starter(
            label="Cinto de segurança obrigatório",
            message="É obrigatório usar cinto de segurança?",
        ),
        cl.Starter(
            label="Telemóvel ao conduzir",
            message="Posso usar telemóvel ao conduzir?",
        ),
        cl.Starter(
            label="Distância mínima para ultrapassar bicicletas",
            message="Qual a distância mínima para ultrapassar bicicletas?",
        ),
    ]


@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("av", _av)

    await cl.Message(
        content=(
            "> ⚠️ **Aviso Legal —** As respostas são geradas automaticamente com base em texto legal "
            "e destinam-se **exclusivamente a fins informativos**. O autor declina qualquer responsabilidade "
            "pela utilização das informações aqui apresentadas. Para efeitos legais, consulte sempre o texto "
            "oficial do Código da Estrada e um profissional qualificado.\n\n"
            "Olá! Sou o **3strada**, o teu assistente do Código da Estrada Português. Como posso ajudar?"
        ),
        author="3strada",
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    av = cl.user_session.get("av")
    pergunta = message.content

    msg = cl.Message(content="", author="3strada")
    await msg.send()

    loop = asyncio.get_event_loop()

    # Verificar se a pergunta é relevante para o Código da Estrada
    relevante = await loop.run_in_executor(_executor, lambda: av.e_pergunta_relevante(pergunta))
    if not relevante:
        msg.content = (
            "Só consigo responder a perguntas sobre o **Código da Estrada português**.\n\n"
            "Tenta perguntar sobre regras de trânsito, limites de velocidade, infrações, sinalização, etc."
        )
        await msg.update()
        return

    resposta, sources = await loop.run_in_executor(_executor, lambda: av.perguntar_ollama(pergunta))

    elements = []
    nomes_usados = set()
    for item in sources:
        titulo = item["artigo"]["titulo"]
        conteudo = item["artigo"]["conteudo"]

        # Chip label: remover . e º para evitar problemas de routing no Chainlit
        # "Artigo 36.º" → "Artigo 36.º" seria o ideal, mas º causa colisões internas
        # Usamos o número extraído: "Artigo 36"
        numero = re.search(r'\d+(?:-[A-Z])?', titulo)
        label = f"Artigo {numero.group()}" if numero else titulo
        # Garantir unicidade entre artigos da mesma resposta
        label_unico = label
        sufixo = 1
        while label_unico in nomes_usados:
            label_unico = f"{label} ({sufixo})"
            sufixo += 1
        nomes_usados.add(label_unico)

        conteudo_artigo = f"**{titulo}**\n\n{conteudo}"
        elements.append(cl.Text(name=label_unico, content=conteudo_artigo, display="side"))

    msg.content = resposta
    msg.elements = elements
    await msg.update()
