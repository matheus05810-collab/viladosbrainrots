# NEXUS AI • Vila dos Brainrots

Chat com IA feito em Streamlit + Google Gemini.

## Arquivos
- `app.py` – o aplicativo inteiro
- `requirements.txt` – bibliotecas
- `plugins/` – agentes extras (um arquivo `.py` por agente, veja `detetive.py`)

## Secrets (Streamlit > Manage app > Settings > Secrets)
```
GEMINI_API_KEY = "obrigatória – aistudio.google.com"
GROQ_API_KEY = "opcional – habilita o provedor Groq"
OPENROUTER_API_KEY = "opcional – habilita o provedor OpenRouter"
```
Nunca coloque chaves dentro do código nem no GitHub.

## Como criar um plugin
Crie `plugins/meu_agente.py` com um dicionário `PLUGIN` contendo
`nome`, `saudacao`, `prompt` e `sugestoes` (veja `plugins/detetive.py`).

## Dados e privacidade
As conversas e memórias ficam só na sessão do navegador (nada é salvo em
servidor). Use "Backup e exportar" para guardar e restaurar.
