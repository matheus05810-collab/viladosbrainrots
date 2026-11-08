import hashlib
import html
import importlib.util
import io
import json
import pathlib
import re
import time
import uuid

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types

# =====================================================================
#  CONFIGURAÇÕES GERAIS
# =====================================================================
NOME_DA_IA = "NEXUS AI • Vila dos Brainrots"
MODELOS_GEMINI = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.5-flash-lite"]
TENTATIVAS_POR_MODELO = 2
TEMPO_LIMITE_MS = 30000
MAX_MENSAGENS_HISTORICO = 20
LIMITE_MENSAGENS = 30          # proteção contra abuso: mensagens por janela
JANELA_SEGUNDOS = 600          # janela de 10 minutos
TAMANHO_MAX_ARQUIVO = 10 * 1024 * 1024

# Outros provedores (aparecem só se a chave estiver nos Secrets)
PROVEDORES_COMPAT = {
    "Groq": {
        "secret": "GROQ_API_KEY",
        "base": "https://api.groq.com/openai/v1",
        "modelos": ["llama-3.3-70b-versatile"],
    },
    "OpenRouter": {
        "secret": "OPENROUTER_API_KEY",
        "base": "https://openrouter.ai/api/v1",
        "modelos": ["meta-llama/llama-3.3-70b-instruct:free"],
    },
}

PAGINAS = ["💬 Chat", "📊 Analisador de dados", "🎞️ Apresentações"]
IDIOMAS_TRADUCAO = ["Inglês", "Espanhol", "Francês", "Alemão", "Italiano", "Japonês", "Português"]

BASE = (
    "Você faz parte da Vila dos Brainrots, uma vila maluca e engraçada da internet. "
    "Fale em português do Brasil, a menos que peçam outro idioma. Suas respostas "
    "devem ser corretas, úteis e fáceis de entender. Se o assunto for sério (saúde, "
    "dinheiro, tristeza, segurança), diminua a zoeira e responda com cuidado, "
    "sugerindo um profissional quando fizer sentido. Não use palavrões nem conteúdo "
    "ofensivo. Não invente fatos: se não souber, diga. Use Markdown; escreva "
    "fórmulas em LaTeX com $...$ ou $$...$$ e tabelas em Markdown quando ajudar."
)

# =====================================================================
#  PERSONAGENS / AGENTES ESPECIALIZADOS
# =====================================================================
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
    "📚 Professor Brainrot (aprendizado)": {
        "saudacao": "Aula começando! Bora aprender sem sofrer, mano!",
        "prompt": (
            "Você é o Professor Brainrot. Explique conteúdos escolares e de "
            "faculdade passo a passo, com exemplos e analogias. No final, ofereça "
            "um mini-exercício para a pessoa praticar."
        ),
        "sugestoes": [
            "Me explica regra de três com exemplos",
            "Cria um mini-quiz de história do Brasil",
            "Me ajuda a montar um plano de estudos para a semana",
        ],
    },
    "💻 Dev Brainrot (programação)": {
        "saudacao": "Bora codar! Me manda seu código ou sua ideia, mano!",
        "prompt": (
            "Você é o Dev Brainrot. Ajude com programação: explique conceitos, "
            "escreva e corrija código e comente o que cada parte faz. Use blocos "
            "de código com a linguagem indicada. Prefira soluções simples e seguras."
        ),
        "sugestoes": [
            "Me ensina o básico de Python do zero",
            "Cria um site simples de uma página para mim",
            "Como eu aprendo a criar jogos?",
        ],
    },
    "🧮 Matemático": {
        "saudacao": "Bora resolver conta sem choro! Manda o problema, mano.",
        "prompt": (
            "Você é o Assistente Matemático. Resolva problemas passo a passo, "
            "mostrando as contas em LaTeX, confira o resultado no final e "
            "explique o raciocínio de forma simples."
        ),
        "sugestoes": [
            "Resolve: 2x² - 5x + 3 = 0",
            "Me explica derivadas com um exemplo do dia a dia",
            "Quanto é 15% de desconto em R$ 249,90?",
        ],
    },
    "✍️ Escritor Profissional": {
        "saudacao": "Vamos escrever algo bom. Qual é o texto de hoje, mano?",
        "prompt": (
            "Você é o Escritor Profissional da Vila. Escreva e melhore e-mails, "
            "textos, currículos, cartas e posts com clareza e correção. Quando "
            "for revisar, mostre o texto final e explique as principais mudanças."
        ),
        "sugestoes": [
            "Escreve um e-mail educado pedindo um orçamento",
            "Melhora este texto (vou colar em seguida)",
            "Me ajuda a montar um currículo",
        ],
    },
    "🌍 Tradutor": {
        "saudacao": "Cola o texto aqui e escolha o idioma no painel, mano!",
        "prompt": (
            "Você é o Tradutor da Vila. Traduza o texto da pessoa para o idioma "
            "de destino escolhido, mantendo o sentido e o tom. Mostre só a "
            "tradução e, se houver ambiguidade, uma nota curta."
        ),
        "sugestoes": [
            "Traduz: Bom dia, tudo bem com você?",
            "Como se diz 'estou atrasado' de forma educada?",
            "Traduz este parágrafo (vou colar)",
        ],
    },
    "🧠 Resumidor": {
        "saudacao": "Cola o textão (ou anexa o PDF) que eu resumo, mano!",
        "prompt": (
            "Você é o Resumidor da Vila. Resuma textos e documentos em tópicos "
            "curtos, destaque as ideias principais e, se pedirem, explique de "
            "forma mais simples ou crie perguntas de revisão."
        ),
        "sugestoes": [
            "Resume o arquivo que eu anexei em 5 tópicos",
            "Explica este assunto de forma bem simples",
            "Cria um resumo em formato de cola para prova",
        ],
    },
    "📅 Produtividade": {
        "saudacao": "Bora organizar essa vida! Qual é a bagunça de hoje, mano?",
        "prompt": (
            "Você é o Assistente de Produtividade. Ajude a organizar tarefas, "
            "rotinas, metas, estudos e projetos. Entregue planos práticos, com "
            "prioridades e prazos realistas, em listas e tabelas."
        ),
        "sugestoes": [
            "Monta uma rotina de estudos e treino para a semana",
            "Me ajuda a priorizar minhas tarefas",
            "Cria um plano para terminar um projeto em 7 dias",
        ],
    },
    "🍳 Chef Brainrot (receitas)": {
        "saudacao": "Cozinha aberta! Me fala o que tem na geladeira, mano!",
        "prompt": (
            "Você é o Chef Brainrot. Sugira receitas simples e baratas, com "
            "ingredientes, quantidades e passos. Alerte sobre alergias e "
            "segurança com fogo e alimentos."
        ),
        "sugestoes": [
            "Tenho ovo, arroz e tomate. O que eu faço?",
            "Receita fácil de lanche para a tarde",
            "Ideias de marmita barata para a semana",
        ],
    },
    "📖 Contador de Histórias (criativo)": {
        "saudacao": "Era uma vez... a Vila dos Brainrots! Qual história vamos criar?",
        "prompt": (
            "Você é o Contador de Histórias da Vila. Crie histórias, contos e "
            "roteiros criativos, com personagens marcantes e reviravoltas, "
            "adequados para todas as idades."
        ),
        "sugestoes": [
            "Conta uma história de terror leve na Vila dos Brainrots",
            "Cria um personagem brainrot novo com história de origem",
            "Escreve um final alternativo maluco para Cinderela",
        ],
    },
    "🎮 Gamer Brainrot (jogos)": {
        "saudacao": "Player 2 entrou no jogo! Qual é a missão de hoje?",
        "prompt": (
            "Você é o Gamer Brainrot. Dê dicas de jogos, estratégias, sugestões "
            "de jogos parecidos e ideias de partidas com amigos. Se não tiver "
            "certeza de uma informação atual, avise."
        ),
        "sugestoes": [
            "Me indica jogos parecidos com Minecraft",
            "Ideias de desafios malucos para jogar com amigos",
            "Como melhorar minha mira em jogos de tiro?",
        ],
    },
    "🎬 Criador de Conteúdo": {
        "saudacao": "Câmera, luz, brainrot! Vamos bolar conteúdo, mano!",
        "prompt": (
            "Você é o Criador de Conteúdo da Vila. Gere ideias de vídeos, "
            "roteiros curtos, títulos, legendas e hashtags para TikTok, Reels e "
            "YouTube, com ideias originais."
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
            "Você é o Professor de Inglês da Vila. Ensine vocabulário, gramática "
            "e conversação, com frases em inglês, tradução e pronúncia "
            "aproximada. Corrija erros com gentileza e proponha desafios."
        ),
        "sugestoes": [
            "Me ensina 10 palavras úteis em inglês",
            "Vamos conversar em inglês? Comece com uma pergunta fácil",
            "Qual a diferença entre 'make' e 'do'?",
        ],
    },
}


def carregar_plugins():
    """Carrega agentes extras da pasta plugins/ (um arquivo .py = um agente)."""
    pasta = pathlib.Path(__file__).parent / "plugins"
    if not pasta.is_dir():
        return
    for arq in sorted(pasta.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f"plugin_{arq.stem}", arq)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            p = getattr(mod, "PLUGIN", None)
            if isinstance(p, dict) and all(k in p for k in ("nome", "prompt")):
                MODOS[str(p["nome"])] = {
                    "saudacao": str(p.get("saudacao", "Plugin carregado!")),
                    "prompt": str(p["prompt"]),
                    "sugestoes": list(p.get("sugestoes", []))[:3],
                }
        except Exception:
            continue  # plugin com erro não derruba o app


carregar_plugins()

ZOEIRA = {
    0: "Não use gírias nem piadas. Seja claro, calmo e profissional.",
    1: "Use um tom leve e simpático, com poucas gírias e no máximo um emoji.",
    2: "Use humor, gírias da internet ('mano', 'sinistro', 'ê lasqueira') e emojis.",
    3: "Vá no caos total: gírias, exageros, piadas e muitos emojis, sempre "
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
#  PÁGINA E ESTADO
# =====================================================================
st.set_page_config(page_title="NEXUS AI", page_icon="🧡", layout="wide")
ss = st.session_state


def novo_id():
    return uuid.uuid4().hex[:8]


def nova_conversa():
    cid = novo_id()
    ss.conversas[cid] = {
        "titulo": "Nova conversa", "mensagens": [], "pasta": "",
        "favorita": False, "criada": time.time(),
    }
    ss.atual = cid


def avisar(msg):
    ss.toasts.append(msg)


for chave, padrao in [
    ("conversas", {}), ("pastas", {}), ("memorias", []), ("atual", None),
    ("envios", []), ("uploader_n", 0), ("audio_n", 0), ("ultimo_audio", None),
    ("pendente", None), ("falar", None), ("toasts", []),
]:
    if chave not in ss:
        ss[chave] = padrao
if ss.atual is None or ss.atual not in ss.conversas:
    nova_conversa()

# =====================================================================
#  TEMA CLARO / ESCURO
# =====================================================================
TEMAS = {
    False: {"bg": "#FFFFFF", "texto": "#1F1F1F", "painel": "#FFF4E8", "cartao": "#FFF1E0",
            "input": "#FFFFFF", "sub": "#6B6B6B"},
    True: {"bg": "#121212", "texto": "#F2F2F2", "painel": "#1C1C1E", "cartao": "#232326",
           "input": "#2A2A2E", "sub": "#A0A0A0"},
}
CSS = """
<style>
:root { --laranja: #FF7A00; }
.stApp { background: @bg@; color: @texto@; }
header[data-testid="stHeader"] { background: @bg@; }
header[data-testid="stHeader"] * { color: @texto@; }
[data-testid="stMarkdownContainer"] *, [data-testid="stWidgetLabel"] *,
[data-testid="stCaptionContainer"] *, .stApp label { color: @texto@; }
[data-testid="stCaptionContainer"] * { color: @sub@; }
h1 { color: var(--laranja) !important; text-align: center; font-weight: 900;
     letter-spacing: -1px; }
.faixa, .faixa * { color: #FFFFFF !important; }
.faixa { background: linear-gradient(90deg, #FF7A00, #FF9A3C); text-align: center;
         padding: 12px; border-radius: 16px; font-weight: 700; margin-bottom: 18px;
         box-shadow: 0 4px 14px rgba(255,122,0,.25); }
[data-testid="stSidebar"] { background: @painel@; }
[data-testid="stChatMessage"] { background: @cartao@; border: 1.5px solid var(--laranja);
         border-radius: 16px; animation: aparecer .25s ease-out; }
@keyframes aparecer { from { opacity: 0; transform: translateY(6px); }
                      to { opacity: 1; transform: none; } }
[data-testid="stChatInput"] > div { background: @input@; border: 2px solid var(--laranja);
         border-radius: 16px; }
[data-testid="stChatInput"] textarea { color: @texto@; }
[data-testid="stBottom"] > div { background: @bg@; }
.stApp input, .stApp textarea { background: @input@ !important; color: @texto@ !important; }
[data-baseweb="select"] > div { background: @input@ !important; }
[data-baseweb="select"] * { color: @texto@ !important; }
[data-baseweb="popover"] ul, [data-baseweb="popover"] li { background: @input@ !important;
         color: @texto@ !important; }
[data-testid="stPopoverBody"] { background: @painel@; }
[data-testid="stExpander"] { border: 1px solid var(--laranja); border-radius: 12px;
         background: @painel@; }
[data-testid="stExpander"] summary * { color: @texto@; }
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
         width: 100%; background: @input@; color: var(--laranja);
         border: 1.5px solid var(--laranja); border-radius: 12px; font-weight: 700;
         transition: all .15s ease; }
.stButton button *, .stDownloadButton button *, .stFormSubmitButton button * {
         color: inherit !important; }
.stButton > button:hover, .stDownloadButton > button:hover,
.stFormSubmitButton > button:hover { background: var(--laranja); color: #FFFFFF;
         transform: translateY(-1px); }
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
         background: var(--laranja) !important; color: #FFFFFF !important; }
[data-testid="stChatInputSubmitButton"] { background: var(--laranja) !important; }
@media (max-width: 640px) { h1 { font-size: 1.6rem; } }
</style>
"""
tema_atual = TEMAS[bool(ss.get("tema_escuro", False))]
css = CSS
for k, v in tema_atual.items():
    css = css.replace(f"@{k}@", v)
st.markdown(css, unsafe_allow_html=True)

# =====================================================================
#  CONEXÃO COM OS PROVEDORES
# =====================================================================
try:
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Falta a chave **GEMINI_API_KEY** nos Secrets do Streamlit (veja o README).")
    st.stop()

client = genai.Client(api_key=GEMINI_KEY, http_options=types.HttpOptions(timeout=TEMPO_LIMITE_MS))


def tem_segredo(nome):
    try:
        return bool(st.secrets.get(nome))
    except Exception:
        return False


def erro_de_chave(erro):
    return any(t in erro for t in ("401", "403", "API key", "PERMISSION_DENIED"))


# =====================================================================
#  ARQUIVOS E TABELAS
# =====================================================================
def ler_tabela(nome, dados):
    if nome.lower().endswith(".csv"):
        for enc in ("utf-8", "latin-1"):
            for sep in (",", ";"):
                try:
                    df = pd.read_csv(io.BytesIO(dados), sep=sep, encoding=enc)
                    if df.shape[1] > 1 or sep == ";":
                        return df
                except Exception:
                    continue
        return pd.read_csv(io.BytesIO(dados), sep=None, engine="python")
    return pd.read_excel(io.BytesIO(dados))


def tabela_para_texto(nome, df, max_linhas=150):
    return (
        f"Tabela '{nome}': {df.shape[0]} linhas x {df.shape[1]} colunas.\n"
        f"Colunas: {', '.join(map(str, df.columns))}\n\n"
        f"Primeiras linhas (CSV):\n{df.head(max_linhas).to_csv(index=False)}\n"
        f"Estatísticas:\n{df.describe(include='all').to_string()}"
    )


def ler_arquivo(f):
    nome = f.name
    ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
    dados = f.getvalue()
    if len(dados) > TAMANHO_MAX_ARQUIVO:
        avisar(f"⚠️ {nome} passa de 10 MB e foi ignorado.")
        return None
    if ext == "pdf":
        return {"nome": nome, "tipo": "bytes", "mime": "application/pdf", "dados": dados}
    mimes = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
    if ext in mimes:
        return {"nome": nome, "tipo": "bytes", "mime": mimes[ext], "dados": dados}
    try:
        if ext in ("csv", "xlsx", "xls"):
            return {"nome": nome, "tipo": "texto", "texto": tabela_para_texto(nome, ler_tabela(nome, dados))}
        return {"nome": nome, "tipo": "texto", "texto": dados.decode("utf-8", errors="ignore")[:60000]}
    except Exception as e:
        avisar(f"⚠️ Não consegui ler {nome}: {str(e)[:80]}")
        return None


# =====================================================================
#  MONTAGEM DAS MENSAGENS E INSTRUÇÕES
# =====================================================================
def para_gemini(msgs):
    saida = []
    for m in msgs:
        partes = [types.Part(text=m["content"])]
        for a in m.get("arquivos", []):
            if a["tipo"] == "bytes":
                partes.append(types.Part.from_bytes(data=a["dados"], mime_type=a["mime"]))
            else:
                partes.append(types.Part(text=f"[Conteúdo do arquivo {a['nome']}]\n{a['texto']}"))
        saida.append(types.Content(role="user" if m["role"] == "user" else "model", parts=partes))
    return saida


def para_openai(msgs):
    saida = []
    for m in msgs:
        texto = m["content"]
        for a in m.get("arquivos", []):
            if a["tipo"] == "texto":
                texto += f"\n\n[Arquivo {a['nome']}]\n{a['texto']}"
        saida.append({"role": m["role"], "content": texto})
    return saida


def montar_instrucao(cfg, conv):
    partes = [BASE, f"Data de hoje: {time.strftime('%d/%m/%Y')}.", MODOS[cfg["modo"]]["prompt"]]
    if "Tradutor" in cfg["modo"]:
        partes.append(f"Idioma de destino da tradução: {cfg['idioma_destino']}.")
    partes += [ZOEIRA[cfg["zoeira"]], TAMANHO[cfg["tamanho"]]]
    if cfg["raciocinio"]:
        partes.append(
            "MODO RACIOCÍNIO: antes de responder, analise o problema em etapas, "
            "considere alternativas, confira cálculos e conclusões, e só então "
            "apresente a resposta final com um resumo do raciocínio."
        )
    if cfg["usar_web"] and cfg["provedor"] == "Gemini":
        partes.append(
            "MODO PESQUISA: use a busca na web, compare várias fontes, destaque "
            "informações contraditórias entre elas e deixe claro o que é "
            "confirmado e o que é incerto."
        )
    nome = (cfg["perfil_nome"] or "").strip()
    if nome:
        partes.append(f"A pessoa quer ser chamada de {nome}.")
    if (cfg["perfil_instr"] or "").strip():
        partes.append("Instruções personalizadas da pessoa:\n" + cfg["perfil_instr"].strip())
    if (cfg["conhecimento"] or "").strip():
        partes.append("Base de conhecimento fornecida pela pessoa (use como fonte principal quando "
                      "for relevante):\n" + cfg["conhecimento"].strip())
    pasta = conv.get("pasta", "")
    if pasta in ss.pastas and ss.pastas[pasta].get("contexto", "").strip():
        partes.append(f"Projeto '{pasta}'. Contexto persistente do projeto:\n" + ss.pastas[pasta]["contexto"].strip())
    if cfg["usar_mem"] and ss.memorias:
        lista = "\n".join(f"- {m['texto']}" for m in ss.memorias[:40])
        partes.append("Memórias autorizadas da pessoa (use só quando relevante):\n" + lista)
    return "\n\n".join(partes)


# =====================================================================
#  CHAMADAS À IA
# =====================================================================
def coletar_fontes(chunk, estado):
    try:
        for cand in chunk.candidates or []:
            gm = getattr(cand, "grounding_metadata", None)
            if gm and gm.grounding_chunks:
                for gc in gm.grounding_chunks:
                    if gc.web and gc.web.uri:
                        estado["fontes"][gc.web.uri] = gc.web.title or gc.web.uri
    except Exception:
        pass


def stream_gemini(msgs, instrucao, cfg, estado):
    contents = para_gemini(msgs)
    usar_web = cfg["usar_web"]
    modelos = list(MODELOS_GEMINI)
    if cfg["modelo"] in modelos:
        modelos.remove(cfg["modelo"])
        modelos.insert(0, cfg["modelo"])
    ultimo = ""

    def config(web):
        return types.GenerateContentConfig(
            system_instruction=instrucao, temperature=cfg["criatividade"],
            tools=[types.Tool(google_search=types.GoogleSearch())] if web else None,
        )

    for modelo in modelos:
        for _ in range(TENTATIVAS_POR_MODELO):
            recebeu = False
            try:
                for chunk in client.models.generate_content_stream(
                    model=modelo, contents=contents, config=config(usar_web)
                ):
                    if chunk.text:
                        recebeu = True
                        yield chunk.text
                    coletar_fontes(chunk, estado)
                if recebeu:
                    estado["modelo"] = modelo
                    return
                ultimo = f"{modelo}: resposta vazia"
                break
            except Exception as e:
                erro = str(e)
                ultimo = f"{modelo}: {erro[:200]}"
                if recebeu:
                    estado["erro"] = ultimo
                    yield "\n\n⚠️ A resposta foi interrompida. Tente de novo."
                    return
                if erro_de_chave(erro):
                    estado["erro"] = ultimo
                    yield MSG_CHAVE
                    return
                if usar_web and ("google_search" in erro.lower() or "tool" in erro.lower()):
                    usar_web = False
                    estado["aviso"] = "A pesquisa na web não está disponível agora; respondi sem ela."
                    continue
                if "404" in erro or "NOT_FOUND" in erro:
                    break
                time.sleep(1.5)
    estado["erro"] = ultimo
    yield MSG_SOBRECARGA


def stream_compat(msgs, instrucao, cfg, estado):
    prov = PROVEDORES_COMPAT[cfg["provedor"]]
    chave = st.secrets[prov["secret"]]
    try:
        r = requests.post(
            f"{prov['base']}/chat/completions",
            headers={"Authorization": f"Bearer {chave}"},
            json={
                "model": cfg["modelo"],
                "messages": [{"role": "system", "content": instrucao}] + para_openai(msgs),
                "temperature": cfg["criatividade"],
            },
            timeout=45,
        )
        if r.status_code != 200:
            estado["erro"] = f"{cfg['modelo']}: {r.status_code} {r.text[:200]}"
            yield MSG_CHAVE if r.status_code in (401, 403) else MSG_SOBRECARGA
            return
        estado["modelo"] = cfg["modelo"]
        yield r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        estado["erro"] = f"{cfg['modelo']}: {str(e)[:200]}"
        yield MSG_SOBRECARGA


def chamar_simples(contents, instrucao=None, json_mode=False, temperatura=0.7):
    """Chamada única ao Gemini (usada em transcrição, dados e apresentações)."""
    cfg = types.GenerateContentConfig(
        system_instruction=instrucao, temperature=temperatura,
        response_mime_type="application/json" if json_mode else None,
    )
    ultimo = ""
    for modelo in MODELOS_GEMINI:
        for _ in range(TENTATIVAS_POR_MODELO):
            try:
                r = client.models.generate_content(model=modelo, contents=contents, config=cfg)
                if r.text:
                    return r.text, ""
                break
            except Exception as e:
                erro = str(e)
                ultimo = f"{modelo}: {erro[:200]}"
                if erro_de_chave(erro):
                    return None, MSG_CHAVE
                if "404" in erro or "NOT_FOUND" in erro:
                    break
                time.sleep(1.5)
    return None, ultimo or MSG_SOBRECARGA


def transcrever(dados):
    texto, _ = chamar_simples(
        [types.Part.from_bytes(data=dados, mime_type="audio/wav"),
         "Transcreva este áudio fielmente. Responda apenas com a transcrição, no idioma falado."],
        temperatura=0.0,
    )
    return (texto or "").strip()


# =====================================================================
#  VOZ (síntese de fala no navegador)
# =====================================================================
def falar(texto):
    limpo = re.sub(r"```.*?```", " bloco de código. ", texto, flags=re.S)
    limpo = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", limpo)
    limpo = re.sub(r"[*_#`>|~$]", "", limpo)[:1800]
    texto_js = json.dumps(limpo).replace("</", "<\\/")
    js = f"""<script>
try {{
  var w = window.parent || window;
  var s = w.speechSynthesis; var U = w.SpeechSynthesisUtterance;
  s.cancel();
  var u = new U({texto_js});
  u.lang = {json.dumps(ss.get("idioma_voz", "pt-BR"))};
  u.rate = {float(ss.get("vel_voz", 1.0))}; u.pitch = {float(ss.get("tom_voz", 1.0))};
  s.speak(u);
}} catch (e) {{}}
</script>"""
    components.html(js, height=0)


def parar_voz():
    components.html(
        "<script>try{(window.parent||window).speechSynthesis.cancel();}catch(e){}</script>", height=0
    )


# =====================================================================
#  LIMITE DE USO
# =====================================================================
def dentro_do_limite():
    agora = time.time()
    ss.envios = [t for t in ss.envios if agora - t < JANELA_SEGUNDOS]
    if len(ss.envios) >= LIMITE_MENSAGENS:
        return False
    ss.envios.append(agora)
    return True


# =====================================================================
#  BACKUP
# =====================================================================
def msg_limpa(m):
    return {k: v for k, v in m.items() if k != "arquivos"}


def exportar_backup():
    return json.dumps(
        {
            "conversas": {cid: {**c, "mensagens": [msg_limpa(m) for m in c["mensagens"]]}
                          for cid, c in ss.conversas.items()},
            "pastas": ss.pastas,
            "memorias": ss.memorias,
        },
        ensure_ascii=False, indent=2,
    )


def importar_backup(dados):
    for cid, c in dados.get("conversas", {}).items():
        if not isinstance(c, dict):
            continue
        c.setdefault("titulo", "Conversa")
        c.setdefault("mensagens", [])
        c.setdefault("pasta", "")
        c.setdefault("favorita", False)
        c.setdefault("criada", time.time())
        c["mensagens"] = [m for m in c["mensagens"]
                          if isinstance(m, dict) and m.get("role") in ("user", "assistant")
                          and isinstance(m.get("content"), str)]
        ss.conversas[str(cid)] = c
    for nome, p in dados.get("pastas", {}).items():
        ss.pastas[str(nome)] = {"contexto": str(p.get("contexto", ""))}
    existentes = {m["texto"] for m in ss.memorias}
    for mem in dados.get("memorias", []):
        t = str(mem.get("texto", "")).strip()
        if t and t not in existentes:
            ss.memorias.append({"id": novo_id(), "texto": t})


def conversa_md(conv):
    linhas = [f"# {conv['titulo']}\n"]
    for m in conv["mensagens"]:
        linhas.append(f"**{'Você' if m['role'] == 'user' else 'IA'}:**\n\n{m['content']}\n")
        for uri, titulo in m.get("fontes", []):
            linhas.append(f"- Fonte: [{titulo}]({uri})")
    return "\n".join(linhas)


# =====================================================================
#  BARRA LATERAL
# =====================================================================
for t in ss.toasts:
    st.toast(t)
ss.toasts = []

with st.sidebar:
    st.markdown("### 🧡 NEXUS AI")
    st.toggle("🌙 Tema escuro", key="tema_escuro")
    st.radio("Ir para", PAGINAS, key="pagina", label_visibility="collapsed")
    if st.button("➕ Nova conversa", key="btn_nova"):
        nova_conversa()
        st.rerun()
    busca = st.text_input("Buscar", key="busca", placeholder="🔎 Buscar no histórico",
                          label_visibility="collapsed")
    lista_box = st.container(height=300)

cfg = {}
with st.sidebar.expander("⚙️ Modelo e modos"):
    provedores = ["Gemini"] + [p for p, c in PROVEDORES_COMPAT.items() if tem_segredo(c["secret"])]
    cfg["provedor"] = st.selectbox("Provedor de IA", provedores, key="provedor")
    if cfg["provedor"] == "Gemini":
        opcoes = ["Automático (com reserva)"] + MODELOS_GEMINI
    else:
        opcoes = PROVEDORES_COMPAT[cfg["provedor"]]["modelos"]
    cfg["modelo"] = st.selectbox("Modelo", opcoes, key=f"modelo_{cfg['provedor']}")
    cfg["modo"] = st.selectbox("Personagem / agente", list(MODOS.keys()), key="modo_sel")
    if "Tradutor" in cfg["modo"]:
        cfg["idioma_destino"] = st.selectbox("Traduzir para", IDIOMAS_TRADUCAO, key="idioma_destino")
    else:
        cfg["idioma_destino"] = ""
    cfg["usar_web"] = st.toggle(
        "🌐 Pesquisa na web (com fontes)", key="usar_web",
        help="Só no provedor Gemini. A IA busca informações atuais e mostra as fontes.",
    )
    cfg["raciocinio"] = st.toggle("🧩 Raciocínio avançado", key="raciocinio",
                                  help="A IA analisa em etapas e confere a resposta (mais lento).")
    cfg["zoeira"] = st.select_slider("Nível de zoeira", options=[0, 1, 2, 3], value=2,
                                     format_func=lambda x: NOMES_ZOEIRA[x], key="zoeira")
    cfg["tamanho"] = st.radio("Tamanho da resposta", list(TAMANHO.keys()), index=1,
                              horizontal=True, key="tamanho")
    cfg["criatividade"] = st.slider("Criatividade", 0.0, 1.5, 0.8, 0.1, key="criatividade",
                                    help="Baixa = precisa e previsível. Alta = criativa.")

with st.sidebar.expander("👤 Perfil e personalização"):
    cfg["perfil_nome"] = st.text_input("Como a IA deve te chamar?", key="perfil_nome")
    cfg["perfil_instr"] = st.text_area("Instruções personalizadas", key="perfil_instr", height=90,
                                       placeholder="Ex.: explique sempre com exemplos de futebol")
    cfg["conhecimento"] = st.text_area("🧠 Cérebro personalizado (textos, regras, lore...)",
                                       key="conhecimento", height=120, max_chars=8000)

with st.sidebar.expander("📁 Pastas e projetos"):
    st.caption("Cada pasta pode ter um contexto fixo que a IA lembra em todas as conversas dela.")
    with st.form("form_pasta", clear_on_submit=True):
        nome_pasta = st.text_input("Nome da nova pasta")
        if st.form_submit_button("Criar pasta") and nome_pasta.strip():
            ss.pastas.setdefault(nome_pasta.strip()[:30], {"contexto": ""})
            avisar("📁 Pasta criada!")
            st.rerun()
    if ss.pastas:
        alvo = st.selectbox("Editar pasta", list(ss.pastas.keys()), key="pasta_edit")
        ss.pastas[alvo]["contexto"] = st.text_area(
            "Contexto do projeto", value=ss.pastas[alvo]["contexto"], key=f"ctx_{alvo}", height=100)
        if st.button("🗑️ Apagar esta pasta", key="del_pasta"):
            for c in ss.conversas.values():
                if c["pasta"] == alvo:
                    c["pasta"] = ""
            del ss.pastas[alvo]
            st.rerun()

with st.sidebar.expander("🧠 Memória"):
    cfg["usar_mem"] = st.toggle("Usar memórias nas respostas", value=True, key="usar_mem")
    st.caption("Pelo chat: escreva /lembrar seguido do que quer guardar. Você pode editar ou apagar abaixo.")
    for mem in list(ss.memorias):
        c1, c2 = st.columns([5, 2])
        mem["texto"] = c1.text_input("memória", value=mem["texto"], key=f"mem_{mem['id']}",
                                     label_visibility="collapsed")
        if c2.button("🗑️", key=f"delmem_{mem['id']}"):
            ss.memorias.remove(mem)
            st.rerun()
    with st.form("form_mem", clear_on_submit=True):
        nova_mem = st.text_input("Nova memória")
        if st.form_submit_button("➕ Adicionar") and nova_mem.strip():
            ss.memorias.append({"id": novo_id(), "texto": nova_mem.strip()})
            st.rerun()
    if ss.memorias and st.button("Apagar todas as memórias", key="del_mems"):
        ss.memorias = []
        st.rerun()
    st.caption("🔒 As memórias ficam só nesta sessão do navegador, a menos que você baixe o backup.")

with st.sidebar.expander("📎 Arquivos"):
    st.caption("PDF, imagens, textos, CSV e Excel. Seguem junto com a próxima mensagem.")
    arquivos_up = st.file_uploader(
        "Anexar", accept_multiple_files=True, key=f"up_{ss.uploader_n}",
        type=["pdf", "png", "jpg", "jpeg", "webp", "txt", "md", "csv", "xlsx", "xls", "json", "py", "js", "html"],
        label_visibility="collapsed",
    )

with st.sidebar.expander("🔊 Voz"):
    st.toggle("Ler respostas em voz alta", key="falar_resp")
    st.selectbox("Idioma da voz", ["pt-BR", "en-US", "es-ES", "fr-FR"], key="idioma_voz")
    st.slider("Velocidade", 0.5, 2.0, 1.0, 0.1, key="vel_voz")
    st.slider("Tom", 0.5, 2.0, 1.0, 0.1, key="tom_voz")
    if st.button("⏹ Parar voz", key="btn_parar"):
        parar_voz()
    st.caption("A voz usa o seu navegador; as opções de voz variam conforme o aparelho.")

with st.sidebar.expander("💾 Backup e exportar"):
    st.download_button("📥 Baixar tudo (backup .json)", exportar_backup(),
                       file_name="nexus-backup.json", mime="application/json")
    conv_atual = ss.conversas[ss.atual]
    if conv_atual["mensagens"]:
        st.download_button("📄 Baixar esta conversa (.md)", conversa_md(conv_atual),
                           file_name="conversa.md", mime="text/markdown")
    up = st.file_uploader("Restaurar backup", type=["json"], key="restaurar")
    if up and st.button("♻️ Restaurar agora", key="btn_restaurar"):
        try:
            importar_backup(json.loads(up.getvalue().decode("utf-8")))
            avisar("♻️ Backup restaurado!")
            st.rerun()
        except Exception:
            st.error("Arquivo de backup inválido.")
    st.caption("Atalhos: Enter envia · Shift+Enter quebra linha.")


# =====================================================================
#  LISTA DE CONVERSAS (histórico, favoritos, pastas)
# =====================================================================
def item_conversa(cid, c):
    c1, c2 = st.columns([5, 1])
    rotulo = ("⭐ " if c["favorita"] else "") + c["titulo"][:26]
    if c1.button(rotulo, key=f"abrir_{cid}", type="primary" if cid == ss.atual else "secondary"):
        ss.atual = cid
        st.rerun()
    with c2.popover("⋯"):
        novo = st.text_input("Nome", value=c["titulo"], key=f"ren_{cid}_{c['titulo']}")
        if novo.strip() and novo.strip() != c["titulo"]:
            c["titulo"] = novo.strip()[:60]
        c["favorita"] = st.toggle("⭐ Favorita", value=c["favorita"], key=f"fav_{cid}")
        opcoes = ["(sem pasta)"] + list(ss.pastas.keys())
        atual = c["pasta"] if c["pasta"] in ss.pastas else "(sem pasta)"
        escolha = st.selectbox("Pasta", opcoes, index=opcoes.index(atual), key=f"pst_{cid}")
        c["pasta"] = "" if escolha == "(sem pasta)" else escolha
        if st.button("🗑️ Apagar conversa", key=f"del_{cid}"):
            del ss.conversas[cid]
            if ss.atual == cid or ss.atual not in ss.conversas:
                nova_conversa()
            st.rerun()


def render_lista():
    termo = (busca or "").strip().lower()
    itens = []
    for cid, c in ss.conversas.items():
        if not c["mensagens"] and cid != ss.atual:
            continue
        if termo and termo not in c["titulo"].lower() and not any(
            termo in m["content"].lower() for m in c["mensagens"]
        ):
            continue
        itens.append((cid, c))
    itens.sort(key=lambda x: x[1]["criada"], reverse=True)
    with lista_box:
        if not itens:
            st.caption("Nenhuma conversa encontrada.")
            return
        favs = [x for x in itens if x[1]["favorita"]]
        if favs:
            st.caption("⭐ Favoritas")
            for cid, c in favs:
                item_conversa(cid, c)
        for pasta in ss.pastas:
            grupo = [x for x in itens if not x[1]["favorita"] and x[1]["pasta"] == pasta]
            if grupo:
                st.caption(f"📁 {pasta}")
                for cid, c in grupo:
                    item_conversa(cid, c)
        soltas = [x for x in itens if not x[1]["favorita"] and x[1]["pasta"] not in ss.pastas]
        if soltas:
            st.caption("🕘 Recentes")
            for cid, c in soltas:
                item_conversa(cid, c)


# =====================================================================
#  PÁGINA: CHAT
# =====================================================================
def mostrar_msg(m):
    with st.chat_message(m["role"], avatar="🧡" if m["role"] == "assistant" else None):
        if m.get("voz"):
            st.caption("🎙️ mensagem de voz")
        st.markdown(m["content"])
        if m.get("anexos"):
            st.caption("📎 " + ", ".join(m["anexos"]))
        if m.get("fontes"):
            with st.expander(f"🔗 Fontes ({len(m['fontes'])})"):
                for uri, titulo in m["fontes"]:
                    st.markdown(f"- [{titulo}]({uri})")
        if m.get("aviso"):
            st.caption(m["aviso"])
        if m.get("modelo"):
            st.caption(f"modelo: {m['modelo']}")
        if m.get("erro"):
            st.caption(f"Detalhe técnico: {m['erro']}")


def enviar(texto, voz=False):
    conv = ss.conversas[ss.atual]
    if texto.strip().lower().startswith("/lembrar"):
        mem = texto.strip()[8:].strip()
        if mem:
            ss.memorias.append({"id": novo_id(), "texto": mem})
            avisar("🧠 Memória salva!")
        else:
            avisar("Escreva o que lembrar: /lembrar <texto>")
        st.rerun()
    if not dentro_do_limite():
        st.warning("Calma, mano! Muitas mensagens em pouco tempo. Espere alguns minutos.")
        return

    arquivos = [a for a in (ler_arquivo(f) for f in arquivos_up) if a]
    msg = {"role": "user", "content": texto, "voz": voz,
           "anexos": [a["nome"] for a in arquivos], "arquivos": arquivos}
    conv["mensagens"].append(msg)
    if conv["titulo"] == "Nova conversa":
        conv["titulo"] = texto.strip().replace("\n", " ")[:45] or "Conversa"
    mostrar_msg(msg)

    recentes = [m for m in conv["mensagens"][-MAX_MENSAGENS_HISTORICO:]
                if m["content"] not in (MSG_SOBRECARGA, MSG_CHAVE)]
    while recentes and recentes[0]["role"] != "user":
        recentes.pop(0)

    instrucao = montar_instrucao(cfg, conv)
    estado = {"fontes": {}, "erro": "", "aviso": "", "modelo": ""}
    if cfg["usar_web"] and cfg["provedor"] != "Gemini":
        estado["aviso"] = "A pesquisa na web só funciona com o provedor Gemini."
    gerador = stream_gemini if cfg["provedor"] == "Gemini" else stream_compat

    with st.chat_message("assistant", avatar="🧡"):
        espera = st.empty()
        espera.caption("🧠 A Vila está pensando...")

        def fluxo():
            primeiro = True
            for pedaco in gerador(recentes, instrucao, cfg, estado):
                if primeiro:
                    espera.empty()
                    primeiro = False
                yield pedaco

        resposta = st.write_stream(fluxo())

    conv["mensagens"].append({
        "role": "assistant", "content": resposta or MSG_SOBRECARGA,
        "fontes": [[u, t] for u, t in estado["fontes"].items()],
        "modelo": estado["modelo"], "erro": estado["erro"], "aviso": estado["aviso"],
    })
    ss.uploader_n += 1
    ss.audio_n += 1
    if ss.get("falar_resp") and not estado["erro"]:
        ss.falar = resposta
    st.rerun()


def pagina_chat():
    conv = ss.conversas[ss.atual]
    info = MODOS[cfg["modo"]]
    st.title(f"🧡 {NOME_DA_IA}")
    st.markdown(
        f'<div class="faixa">{html.escape(cfg["modo"])}<br>{html.escape(info["saudacao"])}</div>',
        unsafe_allow_html=True,
    )
    for m in conv["mensagens"]:
        mostrar_msg(m)

    if not conv["mensagens"] and info["sugestoes"]:
        st.caption("💡 Não sabe o que perguntar? Toque em uma ideia:")
        for i, sug in enumerate(info["sugestoes"]):
            if st.button(sug, key=f"sug_{i}"):
                ss.pendente = sug

    with st.expander("🎙️ Falar com a IA (modo voz)"):
        audio = st.audio_input("Grave sua pergunta", key=f"aud_{ss.audio_n}")

    pergunta = st.chat_input("Fala aí, mano... (ou use /lembrar para salvar uma memória)")
    pend = ss.pendente
    ss.pendente = None
    voz = False
    if not pergunta and pend:
        pergunta = pend
    if not pergunta and audio is not None:
        h = hashlib.md5(audio.getvalue()).hexdigest()
        if h != ss.ultimo_audio:
            ss.ultimo_audio = h
            with st.spinner("Transcrevendo seu áudio..."):
                texto = transcrever(audio.getvalue())
            if texto:
                pergunta, voz = texto, True
            else:
                st.warning("Não consegui transcrever o áudio. Tente de novo.")
    if pergunta:
        enviar(pergunta, voz)


# =====================================================================
#  PÁGINA: ANALISADOR DE DADOS
# =====================================================================
def pagina_dados():
    st.title("📊 Analisador de dados")
    arq = st.file_uploader("Envie uma planilha (CSV ou Excel)", type=["csv", "xlsx", "xls"], key="dados_up")
    if not arq:
        st.info("Envie um arquivo para ver a tabela, os gráficos e perguntar à IA sobre os dados.")
        return
    try:
        df = ler_tabela(arq.name, arq.getvalue())
    except Exception as e:
        st.error(f"Não consegui ler o arquivo: {str(e)[:120]}")
        return
    st.caption(f"{df.shape[0]} linhas × {df.shape[1]} colunas")
    st.dataframe(df.head(200))
    with st.expander("Estatísticas"):
        st.dataframe(df.describe(include="all").T.astype(str))

    st.subheader("Gráfico")
    numericas = list(df.select_dtypes("number").columns)
    if numericas:
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo", ["Barras", "Linha", "Área"])
        eixo_x = c2.selectbox("Eixo X", list(df.columns))
        eixos_y = c3.multiselect("Eixo Y (numérico)", numericas, default=numericas[:1])
        if eixos_y:
            dados = df[[eixo_x] + [y for y in eixos_y if y != eixo_x]].dropna().head(500)
            dados = dados.set_index(eixo_x)
            {"Barras": st.bar_chart, "Linha": st.line_chart, "Área": st.area_chart}[tipo](dados)
    else:
        st.caption("Não há colunas numéricas para gráfico.")

    st.subheader("Pergunte à IA sobre os dados")
    pergunta = st.text_area("Sua pergunta", placeholder="Ex.: Qual categoria vende mais? Há valores estranhos?")
    if st.button("🔍 Analisar com IA") and pergunta.strip():
        with st.spinner("Analisando..."):
            texto, erro = chamar_simples(
                f"{tabela_para_texto(arq.name, df)}\n\nPergunta: {pergunta}",
                instrucao=BASE + " Você é um analista de dados. Baseie-se só nos dados fornecidos, "
                          "cite números e diga quando a amostra não basta para concluir.",
            )
        st.markdown(texto or erro)


# =====================================================================
#  PÁGINA: APRESENTAÇÕES
# =====================================================================
def montar_pptx(titulo, subtitulo, slides):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Pt

    prs = Presentation()
    capa = prs.slides.add_slide(prs.slide_layouts[0])
    capa.shapes.title.text = titulo
    capa.placeholders[1].text = subtitulo
    for s in slides:
        sl = prs.slides.add_slide(prs.slide_layouts[1])
        sl.shapes.title.text = str(s.get("titulo", ""))
        tf = sl.placeholders[1].text_frame
        topicos = [str(t) for t in (s.get("topicos") or [])]
        tf.text = topicos[0] if topicos else ""
        for t in topicos[1:]:
            tf.add_paragraph().text = t
        for p in tf.paragraphs:
            for r in p.runs:
                r.font.size = Pt(22)
        if s.get("notas"):
            sl.notes_slide.notes_text_frame.text = str(s["notas"])
    for sl in prs.slides:
        for p in sl.shapes.title.text_frame.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.color.rgb = RGBColor(0xFF, 0x7A, 0x00)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def pagina_apresentacoes():
    st.title("🎞️ Gerador de apresentações")
    tema = st.text_input("Tema da apresentação", placeholder="Ex.: A história dos videogames")
    c1, c2, c3 = st.columns(3)
    n = c1.slider("Nº de slides", 3, 12, 6)
    publico = c2.text_input("Público", value="Estudantes")
    idioma = c3.selectbox("Idioma", ["Português", "Inglês", "Espanhol"])
    if st.button("✨ Gerar apresentação") and tema.strip():
        with st.spinner("Criando seus slides..."):
            texto, erro = chamar_simples(
                f"Crie uma apresentação sobre: {tema}\nPúblico: {publico}\nIdioma: {idioma}\n"
                f"Número de slides de conteúdo (sem contar a capa): {n}.",
                instrucao=(
                    "Responda SOMENTE com JSON válido neste formato: "
                    '{"titulo": "...", "subtitulo": "...", "slides": [{"titulo": "...", '
                    '"topicos": ["3 a 5 tópicos curtos"], "notas": "o que falar neste slide"}]}'
                ),
                json_mode=True,
            )
        if not texto:
            st.error(erro)
            return
        try:
            bruto = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.M).strip()
            dados = json.loads(bruto)
            slides = dados["slides"]
            arquivo = montar_pptx(str(dados.get("titulo", tema)), str(dados.get("subtitulo", "")), slides)
        except ModuleNotFoundError:
            st.error("Falta a biblioteca python-pptx no requirements.txt.")
            return
        except Exception as e:
            st.error(f"A IA devolveu um formato inesperado ({str(e)[:80]}). Tente de novo.")
            return
        ss.apresentacao = {"dados": dados, "arquivo": arquivo}

    ap = ss.get("apresentacao")
    if ap:
        st.success("Apresentação pronta!")
        st.download_button("📥 Baixar PowerPoint (.pptx)", ap["arquivo"], file_name="apresentacao.pptx",
                           mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
        st.subheader(ap["dados"].get("titulo", ""))
        for i, s in enumerate(ap["dados"]["slides"], 1):
            with st.expander(f"Slide {i}: {s.get('titulo', '')}"):
                for t in s.get("topicos", []):
                    st.markdown(f"- {t}")
                if s.get("notas"):
                    st.caption(f"Notas: {s['notas']}")


# =====================================================================
#  EXECUÇÃO
# =====================================================================
if ss.pagina == "📊 Analisador de dados":
    pagina_dados()
elif ss.pagina == "🎞️ Apresentações":
    pagina_apresentacoes()
else:
    pagina_chat()

render_lista()

if ss.falar:
    texto_falar = ss.falar
    ss.falar = None
    falar(texto_falar)
