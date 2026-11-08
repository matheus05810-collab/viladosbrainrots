import time
import streamlit as st
from google import genai
from google.genai import types

# ---- Configurações (mude à vontade) ----
NOME_DA_IA = "IA Vila dos Brainrots"
# Lista de modelos: ele tenta o primeiro e, se falhar, passa para o próximo.
# Se algum nome deixar de existir, o app simplesmente pula para o seguinte.
MODELOS = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-2.5-flash-lite"]
TENTATIVAS_POR_MODELO = 2
TEMPO_LIMITE_MS = 20000  # 20 segundos por tentativa
PERSONALIDADE = (
    "Você é a IA da Vila dos Brainrots, uma vila maluca e engraçada cheia de "
    "personagens brainrot. Fale em português do Brasil, com humor, gírias da "
    "internet e energia caótica (pode usar expressões como 'mano', 'tipo assim', "
    "'sinistro', 'ê lasqueira', e emojis). Mesmo com o jeito zoeiro, suas "
    "respostas devem ser corretas, úteis e fáceis de entender: explique de "
    "verdade o que a pessoa perguntar, só com um tom divertido. Se o assunto "
    "for sério (saúde, dinheiro, tristeza), diminua a zoeira e responda com "
    "cuidado. Não use palavrões nem conteúdo ofensivo."
)
SAUDACAO = "Bem-vindo à Vila dos Brainrots! 🧡 Pergunta qualquer coisa, mano!"
MSG_SOBRECARGA = (
    "Eita, a Vila tá lotada de brainrot agora e o servidor engasgou! 😵‍💫 "
    "Espera uns segundinhos e manda de novo, mano."
)
MSG_CHAVE = "Deu ruim na chave da API, mano. Confere os Secrets do Streamlit. 🔑"
# ----------------------------------------

st.set_page_config(page_title=NOME_DA_IA, page_icon="🧡")

# Tema laranja e branco
st.markdown(
    """
    <style>
    :root { --laranja: #FF7A00; --laranja-claro: #FFF1E0; }
    .stApp { background-color: #FFFFFF; color: #2B2B2B; }
    header[data-testid="stHeader"] { background: #FFFFFF; }
    h1 { color: var(--laranja) !important; text-align: center;
         font-weight: 900; letter-spacing: -1px; }
    .faixa { background: var(--laranja); color: #FFFFFF; text-align: center;
             padding: 10px; border-radius: 14px; font-weight: 700;
             margin-bottom: 18px; }
    [data-testid="stChatMessage"] { background: var(--laranja-claro);
             border: 2px solid var(--laranja); border-radius: 16px; }
    [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] span { color: #2B2B2B; }
    [data-testid="stChatInput"] { border: 2px solid var(--laranja);
             border-radius: 14px; background: #FFFFFF; }
    [data-testid="stChatInput"] textarea { color: #2B2B2B; }
    [data-testid="stBottom"] > div { background: #FFFFFF; }
    button[kind="primary"], [data-testid="stChatInputSubmitButton"] {
             background: var(--laranja) !important; color: #FFFFFF !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title(f"🧡 {NOME_DA_IA}")
st.markdown(f'<div class="faixa">{SAUDACAO}</div>', unsafe_allow_html=True)

# A chave fica guardada nos "secrets" do Streamlit, nunca no código
client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options=types.HttpOptions(timeout=TEMPO_LIMITE_MS),
)


def gerar_resposta(historico):
    """Tenta cada modelo, com novas tentativas rápidas. Retorna (texto, erro_tecnico)."""
    ultimo_erro = ""
    for modelo in MODELOS:
        for tentativa in range(TENTATIVAS_POR_MODELO):
            try:
                resposta = client.models.generate_content(
                    model=modelo,
                    contents=historico,
                    config=types.GenerateContentConfig(system_instruction=PERSONALIDADE),
                )
                if resposta.text:
                    return resposta.text, ""
                ultimo_erro = f"{modelo}: resposta vazia"
                break
            except Exception as e:
                erro = str(e)
                ultimo_erro = f"{modelo}: {erro[:200]}"
                if "401" in erro or "403" in erro or "API key" in erro:
                    return MSG_CHAVE, ultimo_erro
                if "404" in erro or "NOT_FOUND" in erro:
                    break  # modelo não existe mais: vai para o próximo
                time.sleep(1.5)
    return MSG_SOBRECARGA, ultimo_erro


if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

for m in st.session_state.mensagens:
    with st.chat_message(m["role"], avatar="🧡" if m["role"] == "assistant" else None):
        st.markdown(m["content"])

pergunta = st.chat_input("Fala aí, mano...")

if pergunta:
    st.session_state.mensagens.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    historico = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in st.session_state.mensagens
        if m["content"] not in (MSG_SOBRECARGA, MSG_CHAVE)
    ]

    with st.chat_message("assistant", avatar="🧡"):
        with st.spinner("A Vila está pensando... 🧠"):
            texto, erro_tecnico = gerar_resposta(historico)
        st.markdown(texto)
        if erro_tecnico:
            st.caption(f"Detalhe técnico: {erro_tecnico}")

    st.session_state.mensagens.append({"role": "assistant", "content": texto})
