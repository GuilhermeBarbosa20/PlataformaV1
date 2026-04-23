# Diretor de Marketing AI (Python Web)

Colaborador virtual com interface web, onde o utilizador escreve uma instrucao e o "Diretor de Marketing" encaminha automaticamente para o agente posterior mais adequado.

## O que este projeto faz

- Recebe um input em linguagem natural.
- Tenta primeiro classificacao autonoma com IA (modelo compatível com OpenAI API).
- Se a IA nao estiver disponivel, usa fallback por palavras-chave.
- Redireciona para um agente especializado:
  - Agente Copywriter
  - Agente Designer
  - Agente Redes sociais
  - Agente Meta Ads
  - Agente Linkedin Ads
  - Agente Google Ads
  - Agente Web Developer
  - Agente Seo
  - Agente GEO
  - Agente Analista de Score
- Devolve um plano de acao com justificacao.

## Como correr

1. Criar ambiente virtual (opcional, recomendado):

```bash
python -m venv .venv
```

2. Ativar ambiente virtual:

- PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Arrancar servidor:

```bash
python -m uvicorn app:app --reload
```

5. Abrir no browser:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Modo autonomo com IA

Por defeito, a fonte principal de processamento do Diretor e a OpenAI:

- `OPENAI_API_KEY=<a_tua_chave>`
- `DIRECTOR_AI_MODEL=gpt-4o-mini` (ou outro modelo OpenAI)

No PowerShell:

```bash
$env:OPENAI_API_KEY="sk-..."
$env:DIRECTOR_AI_MODEL="gpt-4o-mini"
python -m uvicorn app:app --reload
```

Opcionalmente, podes usar um endpoint compativel com OpenAI (ex.: Ollama), mas apenas com ativacao explicita:

- `DIRECTOR_ALLOW_COMPATIBLE_API=true`
- `DIRECTOR_AI_API_URL=http://127.0.0.1:11434/v1/chat/completions`
- `DIRECTOR_AI_MODEL=llama3.1`
- `DIRECTOR_AI_API_KEY` (opcional)

Se a IA nao estiver disponivel ou a resposta vier invalida, o sistema continua a funcionar em modo fallback por palavras-chave.

## Endpoint principal

- `POST /chat`
  - Body JSON:

```json
{
  "user_input": "Quero melhorar a taxa de conversao dos meus anuncios"
}
```
