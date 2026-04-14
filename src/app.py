import sys
import os

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import streamlit as st

st.set_page_config(
    page_title="3strada",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', system-ui, sans-serif;
}

.brand-header {
    display: flex;
    align-items: baseline;
    gap: 14px;
    padding: 2rem 0 0.5rem 0;
}

.brand-logo {
    font-size: 2.8rem;
    font-weight: 700;
    letter-spacing: -1px;
    line-height: 1;
}

.brand-logo .accent {
    color: #009c3b;
}

.brand-logo .name {
    color: #ffffff;
}

.brand-tagline {
    color: #8b95a1;
    font-size: 0.95rem;
    font-weight: 400;
}

.disclaimer-box {
    background: rgba(255, 193, 7, 0.08);
    border-left: 3px solid #ffc107;
    border-radius: 0 6px 6px 0;
    padding: 0.75rem 1rem;
    margin: 1rem 0 1.5rem 0;
    font-size: 0.82rem;
    color: #c9a227;
    line-height: 1.5;
}

.disclaimer-box strong {
    color: #ffc107;
}

.sources-header {
    color: #8b95a1;
    font-size: 0.78rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 1rem 0 0.5rem 0;
    padding-top: 0.75rem;
    border-top: 1px solid rgba(255,255,255,0.07);
}

.rrf-score {
    font-size: 0.75rem;
    color: #8b95a1;
    font-family: monospace;
}

div[data-testid="stExpander"] {
    border-left: 2px solid #009c3b !important;
    border-radius: 0 6px 6px 0 !important;
    background: rgba(0, 156, 59, 0.04) !important;
    margin-bottom: 0.4rem !important;
}

.suggestion-label {
    color: #8b95a1;
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
}

div[data-testid="stChatMessage"] {
    padding: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="A carregar o Código da Estrada...")
def _load_backend():
    import assistente_vetorial as av
    return av


def _render_sources(sources):
    if not sources:
        return
    st.markdown('<div class="sources-header">Artigos consultados — busca híbrida BM25 + vetorial</div>',
                unsafe_allow_html=True)
    for item in sources:
        titulo = item["artigo"]["titulo"]
        conteudo = item["artigo"]["conteudo"]
        relevancia = item["relevancia"]
        distancia = item["distancia"]

        label = f"{titulo}"
        with st.expander(label, expanded=False):
            st.markdown(f'<span class="rrf-score">RRF: {relevancia:.4f}'
                        + (f"  |  dist. semântica: {distancia:.4f}" if distancia is not None else "")
                        + '</span>', unsafe_allow_html=True)
            st.markdown(conteudo)


def _process_question(pergunta, av):
    st.session_state.messages.append({"role": "user", "content": pergunta, "sources": None})

    with st.chat_message("user"):
        st.markdown(pergunta)

    sources = av.retriever.retrieve(pergunta, k=3)

    with st.chat_message("assistant"):
        with st.spinner("A consultar o Código da Estrada..."):
            resposta = av.perguntar_ollama(pergunta)
        st.markdown(resposta)
        _render_sources(sources)

    st.session_state.messages.append({
        "role": "assistant",
        "content": resposta,
        "sources": sources,
    })


# --- Init session state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "_pending_question" not in st.session_state:
    st.session_state._pending_question = None

# --- Header ---
st.markdown("""
<div class="brand-header">
    <span class="brand-logo">
        <span class="accent">3</span><span class="name">strada</span>
    </span>
    <span class="brand-tagline">Assistente do Código da Estrada Português</span>
</div>
""", unsafe_allow_html=True)

# --- Disclaimer ---
st.markdown("""
<div class="disclaimer-box">
    <strong>Aviso Legal —</strong> As respostas fornecidas por esta aplicação são geradas
    automaticamente com base em texto legal e destinam-se <strong>exclusivamente a fins informativos</strong>.
    O autor desta aplicação declina qualquer responsabilidade pela utilização das informações
    aqui apresentadas. Para efeitos legais, consulte sempre o texto oficial do Código da Estrada
    e um profissional qualificado.
</div>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.markdown("### 3strada")
    st.markdown("Assistente baseado em **RAG** (*Retrieval-Augmented Generation*) sobre o Código da Estrada português.")
    st.markdown("---")
    st.markdown("**Modelo:** `llama3.1:8b` via Ollama")
    st.markdown("**Retrieval:** BM25 + ChromaDB com RRF")
    st.markdown("**Artigos indexados:** 200")
    st.markdown("---")
    if st.button("Limpar conversa", use_container_width=True):
        st.session_state.messages = []
        st.session_state._pending_question = None
        st.rerun()

# --- Sugestões (só quando conversa está vazia) ---
if not st.session_state.messages:
    st.markdown('<div class="suggestion-label">Sugestões de perguntas</div>', unsafe_allow_html=True)
    suggestions = [
        "Qual é o limite de velocidade em autoestrada?",
        "É obrigatório usar cinto de segurança?",
        "Posso usar telemóvel ao conduzir?",
        "Qual a distância mínima para ultrapassar bicicletas?",
    ]
    cols = st.columns(2)
    for i, sug in enumerate(suggestions):
        if cols[i % 2].button(sug, use_container_width=True):
            st.session_state._pending_question = sug
            st.rerun()

# --- Histórico ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            _render_sources(msg["sources"])

# --- Input ---
pergunta_input = st.chat_input("Faça a sua pergunta sobre o Código da Estrada...")

# --- Processar pergunta (input ou sugestão) ---
pergunta = pergunta_input or st.session_state._pending_question
if pergunta:
    st.session_state._pending_question = None
    av = _load_backend()
    _process_question(pergunta, av)
