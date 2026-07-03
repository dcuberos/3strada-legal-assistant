import sys
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import chainlit as cl
import assistente_vetorial as _av

_av.init()

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

    # Classificador de relevância e retrieval em paralelo (o retrieval é local,
    # não compete com o Ollama; se a pergunta for irrelevante descarta-se o resultado)
    relevante, sources = await asyncio.gather(
        loop.run_in_executor(_executor, av.e_pergunta_relevante, pergunta),
        loop.run_in_executor(_executor, av.obter_artigos, pergunta),
    )
    if not relevante:
        msg.content = (
            "Só consigo responder a perguntas sobre o **Código da Estrada português**.\n\n"
            "Tenta perguntar sobre regras de trânsito, limites de velocidade, infrações, sinalização, etc."
        )
        await msg.update()
        return

    # Streaming token-a-token: o generator síncrono corre num thread e empurra
    # tokens para uma queue asyncio
    queue = asyncio.Queue()

    def _produzir():
        try:
            for token in av.stream_resposta(pergunta, sources):
                loop.call_soon_threadsafe(queue.put_nowait, token)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(_executor, _produzir)

    while True:
        token = await queue.get()
        if token is None:
            break
        await msg.stream_token(token)

    # Construir um único painel lateral com todos os artigos por ordem de relevância.
    # Usar um único cl.Text evita bugs de routing do Chainlit e garante que o header
    # da seta diz "Artigos Relevantes" em vez do nome interno do elemento.
    elementos_texto = []
    for item in sources:
        titulo = item["artigo"]["titulo"]
        conteudo = item["artigo"]["conteudo"]
        elementos_texto.append(f"**{titulo}**\n\n{conteudo}")

    elements = []
    if elementos_texto:
        conteudo_painel = "\n\n---\n\n".join(elementos_texto)
        elements = [cl.Text(name="Artigos Relevantes", content=conteudo_painel, display="side")]

    msg.elements = elements
    await msg.update()
