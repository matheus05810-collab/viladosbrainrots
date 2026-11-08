import streamlit as st
from google import genai
from google.genai import types

# ---- Configurações (mude à vontade) ----
NOME_DA_IA = "IA Vila dos Brainrots"
MODELO = "gemini-2.5-flash"  # confira o nome atual no Google AI Studio
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
client = genai.Client(api_key=st.secrets["AQ.Ab8RN6IMY9rrsoAX5Xv0Y3_Ba2cKBwjLxEwmUSOWMCpUEDYsZQ"])

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
    ]

    with st.chat_message("assistant", avatar="🧡"):
        try:
            resposta = client.models.generate_content(
                model=MODELO,
                contents=historico,
                config=types.GenerateContentConfig(system_instruction=PERSONALIDADE),
            )
            texto = resposta.text
        except Exception as e:
            texto = f"Eita, deu ruim na Vila: {e}"
        st.markdown(texto)

    st.session_state.mensagens.append({"role": "assistant", "content": texto})
