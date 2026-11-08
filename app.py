import time
import streamlit as st
from google import genai
from google.genai import types

# =====================================================================
#  CONFIGURAÇÕES GERAIS (mude à vontade)
# =====================================================================
NOME_DA_IA = "IA Vila dos Brainrots"
MODELOS = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.5-flash-lite"]
TENTATIVAS_POR_MODELO = 2
TEMPO_LIMITE_MS = 20000      # 20 segundos por tentativa
MAX_MENSAGENS_HISTORICO = 20  # só as últimas mensagens vão para a IA (economiza limite)

BASE = (
    "Você faz parte da Vila dos Brainrots, uma vila maluca e engraçada da internet. "
    "Fale em português do Brasil. Suas respostas devem ser corretas, úteis e fáceis "
    "de entender. Se o assunto for sério (saúde, dinheiro, tristeza, segurança), "
    "diminua a zoeira e responda com cuidado, sugerindo procurar um profissional "
    "quando fizer sentido. Não use palavrões nem conteúdo ofensivo."
)

# Cada modo é um "personagem" da vila, com foco numa especialidade.
MODOS = {
    "🧡 Vila dos Brainrots (geral)": {
        "saudacao": "Bem-vindo à Vila dos Brainrots! Pergunta qualquer coisa, mano!",
        "prompt": "Você é a IA geral da Vila: responde sobre qualquer assunto.",
        "sugestoes": [
            "Me explica um assunto difícil como se eu tivesse 10 anos",
            "Me conta uma curiosidade maluca",
            "Me ajuda a escolher entre duas opções",
        ],
    },
    "📚 Professor Brainrot (estudos)": {
        "saudacao": "Aula começando! Bora aprender sem sofrer, mano!",
        "prompt": (
            "Você é o Professor Brainrot. Explique conteúdos escolares e de "
            "faculdade passo a passo, com exemplos e analogias divertidas. No "
            "final, ofereça um mini-exercício para a pessoa praticar."
        ),
        "sugestoes": [
            "Me explica regra de três com exemplos",
            "Cria um mini-quiz de história do Brasil",
            "Me ajuda a montar um plano de estudos para a semana",
        ],
    },
    "🍳 Chef Brainrot (receitas)": {
        "saudacao": "Cozinha aberta! Me fala o que tem na geladeira, mano!",
        "prompt": (
            "Você é o Chef Brainrot. Sugira receitas simples e baratas, com "
            "ingredientes, quantidades e modo de preparo em passos. Pergunte o que "
            "a pessoa tem em casa quando ajudar. Alerte sobre alergias e "
            "segurança com fogo e alimentos."
        ),
        "sugestoes": [
            "Tenho ovo, arroz e tomate. O que eu faço?",
            "Receita fácil de lanche para a tarde",
            "Ideias de marmita barata para a semana",
        ],
    },
    "📖 Contador de Histórias": {
        "saudacao": "Era uma vez... a Vila dos Brainrots! Qual história vamos criar?",
        "prompt": (
            "Você é o Contador de Histórias da Vila. Crie histórias, contos e "
            "roteiros criativos, com personagens marcantes e reviravoltas. Mantenha "
            "o conteúdo adequado para todas as idades."
        ),
        "sugestoes": [
            "Conta uma história de terror leve na Vila dos Brainrots",
            "Cria um personagem brainrot novo com história de origem",
            "Escreve um final alternativo maluco para Cinderela",
        ],
    },
    "💻 Dev Brainrot (programação)": {
        "saudacao": "Bora codar! Me manda seu código ou sua ideia, mano!",
        "prompt": (
            "Você é o Dev Brainrot. Ajude com programação: explique conceitos, "
            "escreva e corrija código, e comente o que cada parte faz. Use blocos "
            "de código e indique a linguagem. Prefira soluções simples."
        ),
        "sugestoes": [
            "Me ensina o básico de Python do zero",
            "Cria um site simples de uma página para mim",
            "Como eu aprendo a criar jogos?",
        ],
    },
    "🎮 Gamer Brainrot (jogos)": {
        "saudacao": "Player 2 entrou no jogo! Qual é a missão de hoje?",
        "prompt": (
            "Você é o Gamer Brainrot. Dê dicas de jogos, estratégias, builds, "
            "sugestões de jogos parecidos e ideias de partidas com amigos. Se não "
            "tiver certeza de uma informação atual de um jogo, avise."
        ),
        "sugestoes": [
            "Me indica jogos parecidos com Minecraft",
            "Ideias de desafios malucos para jogar com amigos",
            "Como melhorar minha mira em jogos de tiro?",
        ],
    },
    "🎬 Criador de Conteúdo (ideias)": {
        "saudacao": "Câmera, luz, brainrot! Vamos bolar conteúdo viral, mano!",
        "prompt": (
            "Você é o Criador de Conteúdo da Vila. Gere ideias de vídeos, roteiros "
            "curtos, títulos, legendas, hashtags e formatos para TikTok, Reels e "
            "YouTube. Dê ideias originais e dicas para crescer de forma saudável."
        ),
        "sugestoes": [
            "10 ideias de vídeos curtos sobre a Vila dos Brainrots",
            "Escreve um roteiro de 30 segundos engraçado",
            "Cria 5 títulos chamativos para um vídeo de games",
        ],
    },
    "🇺🇸 Professor de Inglês": {
        "saudacao": "Let's go! Vamos treinar inglês de um jeito divertido, mano!",
        "prompt": (
            "Você é o Professor de Inglês da Vila. Ensine vocabulário, gramática e "
            "conversação. Mostre frases em inglês com tradução e pronúncia "
            "aproximada. Corrija os erros da pessoa com gentileza e proponha "
            "pequenos desafios."
        ),
        "sugestoes": [
            "Me ensina 10 palavras úteis em inglês",
            "Vamos conversar em inglês? Comece com uma pergunta fácil",
            "Qual a diferença entre 'make' e 'do'?",
        ],
    },
    "🧠 Resumidor": {
        "saudacao": "Cola o textão aqui que eu resumo pra você, mano!",
        "prompt": (
            "Você é o Resumidor da Vila. Resuma textos longos em tópicos curtos, "
            "destaque as ideias principais e, se a pessoa pedir, explique em "
            "linguagem mais simples ou crie perguntas de revisão."
        ),
        "sugestoes": [
            "Resume um texto em 5 tópicos (vou colar em seguida)",
            "Explica este assunto de forma bem simples",
            "Cria um resumo em formato de cola para prova",
        ],
    },
}

ZOEIRA = {
    0: "Não use gírias nem piadas. Seja claro, calmo e profissional.",
    1: "Use um tom leve e simpático, com poucas gírias e no máximo um emoji.",
    2: "Use humor, gírias da internet ('mano', 'sinistro', 'ê lasqueira') e emojis.",
    3: "Vá no caos total: gírias, exageros, piadas e muitos emojis, mas sempre "
       "entregando a resposta certa.",
}
NOMES_ZOEIRA = {0: "Sério", 1: "Leve", 2: "Zoeiro", 3: "Caos total"}

TAMANHO = {
    "Curta": "Responda de forma bem curta e direta (no máximo 3 frases).",
    "Média": "Responda com tamanho médio, explicando o necessário.",
    "Longa": "Responda de forma detalhada, com exemplos e passo a passo.",
}

MSG_SOBRECARGA = (
    "Eita, a Vila tá lotada de brainrot agora e o servidor engasgou! 😵‍💫 "
    "Espera uns segundinhos e manda de novo, mano."
)
MSG_CHAVE = "Deu ruim na chave da API, mano. Confere os Secrets do Streamlit. 🔑"

# =====================================================================
#  VISUAL (laranja e branco)
# =====================================================================
st.set_page_config(page_title=NOME_DA_IA, page_icon="🧡", layout="centered")

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
    [data-testid="stSidebar"] { background: var(--laranja-claro); }
    [data-testid="stSidebar"] * { color: #2B2B2B; }
    [data-testid="stChatMessage"] { background: var(--laranja-claro);
             border: 2px solid var(--laranja); border-radius: 16px; }
    [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] span { color: #2B2B2B; }
    [data-testid="stChatInput"] { border: 2px solid var(--laranja);
             border-radius: 14px; background: #FFFFFF; }
    [data-testid="stChatInput"] textarea { color: #2B2B2B; }
    [data-testid="stBottom"] > div { background: #FFFFFF; }
    .stButton > button, .stDownloadButton > button {
             background: #FFFFFF; color: var(--laranja);
             border: 2px solid var(--laranja); border-radius: 12px;
             font-weight: 700; }
    .stButton > button:hover, .stDownloadButton > button:hover {
             background: var(--laranja); color: #FFFFFF; }
    [data-testid="stChatInputSubmitButton"] {
             background: var(--laranja) !important; color: #FFFFFF !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =====================================================================
#  MENU LATERAL (funções e ajustes)
# =====================================================================
with st.sidebar:
    st.header("🧡 Painel da Vila")

    modo = st.selectbox("Escolha o personagem", list(MODOS.keys()))

    zoeira = st.select_slider(
        "Nível de zoeira",
        options=[0, 1, 2, 3],
        value=2,
        format_func=lambda x: NOMES_ZOEIRA[x],
    )
    tamanho = st.radio("Tamanho da resposta", list(TAMANHO.keys()), index=1, horizontal=True)
    criatividade = st.slider(
        "Criatividade", 0.0, 1.5, 0.8, 0.1,
        help="Baixa = mais certinha e previsível. Alta = mais criativa e maluca.",
    )

    with st.expander("🧠 Cérebro personalizado"):
        st.caption(
            "Cole aqui textos, regras, informações do seu negócio, lore da Vila, "
            "personagens... A IA vai usar isso como base das respostas."
        )
        conhecimento = st.text_area("Conhecimento extra", height=160, max_chars=6000)

    with st.expander("🖼️ Mandar uma imagem"):
        imagem = st.file_uploader(
            "A IA vai olhar a imagem na próxima mensagem", type=["png", "jpg", "jpeg", "webp"]
        )
        if imagem:
            st.image(imagem, use_container_width=True)

    st.divider()
    col1, col2 = st.columns(2)
    limpar = col1.button("🗑️ Limpar", use_container_width=True)

# Trocar de personagem começa uma conversa nova
if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
if st.session_state.get("modo_atual") != modo:
    st.session_state.modo_atual = modo
    st.session_state.mensagens = []
if limpar:
    st.session_state.mensagens = []

with st.sidebar:
    if st.session_state.mensagens:
        texto_conversa = "\n\n".join(
            f"{'VOCÊ' if m['role'] == 'user' else 'IA'}: {m['content']}"
            for m in st.session_state.mensagens
        )
        col2.download_button(
            "💾 Baixar", texto_conversa, file_name="conversa-vila-dos-brainrots.txt",
            use_container_width=True,
        )

info = MODOS[modo]

# =====================================================================
#  CABEÇALHO
# =====================================================================
st.title(f"🧡 {NOME_DA_IA}")
st.markdown(f'<div class="faixa">{modo}<br>{info["saudacao"]}</div>', unsafe_allow_html=True)

# =====================================================================
#  CONEXÃO COM A IA
# =====================================================================
# A chave fica guardada nos "secrets" do Streamlit, nunca no código
client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options=types.HttpOptions(timeout=TEMPO_LIMITE_MS),
)


def montar_instrucao():
    partes = [BASE, info["prompt"], ZOEIRA[zoeira], TAMANHO[tamanho]]
    if conhecimento.strip():
        partes.append(
            "Use as informações abaixo como base principal das suas respostas "
            "(se a pergunta não tiver relação, responda normalmente):\n"
            + conhecimento.strip()
        )
    return "\n\n".join(partes)


def gerar_resposta(historico):
    """Tenta cada modelo, com novas tentativas rápidas. Retorna (texto, erro_tecnico)."""
    ultimo_erro = ""
    config = types.GenerateContentConfig(
        system_instruction=montar_instrucao(), temperature=criatividade
    )
    for modelo in MODELOS:
        for _ in range(TENTATIVAS_POR_MODELO):
            try:
                resposta = client.models.generate_content(
                    model=modelo, contents=historico, config=config
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


# =====================================================================
#  CONVERSA
# =====================================================================
for m in st.session_state.mensagens:
    with st.chat_message(m["role"], avatar="🧡" if m["role"] == "assistant" else None):
        st.markdown(m["content"])

# Botões de sugestão (só aparecem no começo da conversa)
if "pendente" not in st.session_state:
    st.session_state.pendente = None

if not st.session_state.mensagens:
    st.caption("💡 Não sabe o que perguntar? Toca em uma ideia:")
    for i, sugestao in enumerate(info["sugestoes"]):
        if st.button(sugestao, key=f"sug_{i}", use_container_width=True):
            st.session_state.pendente = sugestao

pergunta = st.chat_input("Fala aí, mano...")
if st.session_state.pendente and not pergunta:
    pergunta = st.session_state.pendente
st.session_state.pendente = None

if pergunta:
    st.session_state.mensagens.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)
        if imagem:
            st.image(imagem, width=220)

    recentes = [
        m for m in st.session_state.mensagens[-MAX_MENSAGENS_HISTORICO:]
        if m["content"] not in (MSG_SOBRECARGA, MSG_CHAVE)
    ]
    historico = []
    for i, m in enumerate(recentes):
        partes = [types.Part(text=m["content"])]
        # a imagem vai junto só com a mensagem atual (a última)
        if imagem and i == len(recentes) - 1 and m["role"] == "user":
            partes.append(
                types.Part.from_bytes(data=imagem.getvalue(), mime_type=imagem.type)
            )
        historico.append(
            types.Content(role="user" if m["role"] == "user" else "model", parts=partes)
        )

    with st.chat_message("assistant", avatar="🧡"):
        with st.spinner("A Vila está pensando... 🧠"):
            texto, erro_tecnico = gerar_resposta(historico)
        st.markdown(texto)
        if erro_tecnico:
            st.caption(f"Detalhe técnico: {erro_tecnico}")

    st.session_state.mensagens.append({"role": "assistant", "content": texto})
