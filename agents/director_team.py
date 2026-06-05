"""Orquestração multi-agente do Diretor de Marketing.

O Diretor deixa de ser apenas um router de triagem: planeia trabalho para vários
especialistas, executa-os internamente (quando possível) e devolve uma resposta
agregada numa única conversa com o utilizador.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from openai import OpenAI

from agents.copywriter import copywriter_agent
from agents.designer import designer_agent
from agents.social_media import social_media_agent

MAX_TEAM_AGENTS = 5

COPYWRITER_AGENT = "Agente Copywriter"
DESIGNER_AGENT = "Agente Designer"
SOCIAL_AGENTS = frozenset({"Agente Redes sociais", "Agente Meta Ads"})
LINKEDIN_AGENTS = frozenset({"Agente LinkedIn (perfil)", "Agente Linkedin Ads"})
def build_conversation_brief(messages: Sequence[Dict[str, str]]) -> str:
    """Junta o histórico da chatroom num único brief para a equipa.

    Argumentos:
        messages: Histórico com `role` (`user`/`assistant`) e `content`.

    Retorno:
        Texto concatenado com os turnos relevantes da conversa.
    """

    lines: List[str] = []
    for message in messages:
        role = str(message.get("role", "")).strip()
        content = str(message.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        label = "Utilizador" if role == "user" else "Diretor"
        lines.append(f"{label}: {content}")
    return "\n".join(lines).strip()


def infer_team_agents_from_keywords(
    normalized_input: str,
    routing_map: Dict[str, List[str]],
    normalize_keyword: Callable[[str], str],
    resolve_linkedin: Callable[[str], Optional[Tuple[str, int]]],
) -> List[str]:
    """Infere vários agentes relevantes por correspondência de palavras-chave.

    Argumentos:
        normalized_input: Pedido do utilizador já normalizado.
        routing_map: Mapa agente → palavras-chave do Diretor.
        normalize_keyword: Função que normaliza cada keyword do mapa.
        resolve_linkedin: Função que resolve rotas LinkedIn perfil vs ads.

    Retorno:
        Lista ordenada por relevância (máximo `MAX_TEAM_AGENTS` agentes).
    """

    scores: List[Tuple[int, str]] = []
    for agent, keywords in routing_map.items():
        score = sum(1 for keyword in keywords if normalize_keyword(keyword) in normalized_input)
        if score > 0:
            scores.append((score, agent))
    linkedin_route = resolve_linkedin(normalized_input)
    if linkedin_route is not None:
        linkedin_agent, linkedin_score = linkedin_route
        if linkedin_score > 0:
            scores.append((linkedin_score + 2, linkedin_agent))

    scores.sort(key=lambda item: (-item[0], item[1]))
    selected = [agent for _, agent in scores[:MAX_TEAM_AGENTS]]
    if selected:
        return selected

    if linkedin_route is not None:
        return [linkedin_route[0]]
    return []


def plan_team_with_llm(
    client: OpenAI,
    model: str,
    agent_catalog: Sequence[str],
    linkedin_guidance: str,
    messages: Sequence[Dict[str, str]],
    language: str,
    keyword_agents: List[str],
) -> Dict[str, Any]:
    """Pede ao LLM um plano de equipa multi-agente para o pedido atual.

    Argumentos:
        client: Cliente OpenAI já autenticado.
        model: Identificador do modelo (ex.: `gpt-4o-mini`).
        agent_catalog: Nomes canónicos dos agentes disponíveis.
        linkedin_guidance: Regras de desambiguação LinkedIn perfil vs ads.
        messages: Histórico da conversa do Diretor.
        language: Idioma da resposta ao utilizador.
        keyword_agents: Sugestão de agentes vindos do fallback por keywords.

    Retorno:
        Dicionário com `needs_clarification`, `reply`, `execution_plan` e
        `team_assignments` (lista de `{agent_name, task_brief}`).
    """

    allowed = ", ".join(agent_catalog)
    conversation = build_conversation_brief(messages)
    keyword_hint = ", ".join(keyword_agents) if keyword_agents else "nenhum"
    internal_only = set(agent_catalog) <= {"Agente Copywriter", "Agente Designer"}
    scope_rules = (
        "Nesta chatroom o Diretor só executa copy (Copywriter) e criativo visual (Designer). "
        "Pedidos de Instagram, LinkedIn, análise de perfil, publicação ou calendário "
        "NÃO são tratados aqui — o utilizador será encaminhado para o agente de rede. "
        if internal_only
        else "Para campanhas com copy e design, ativa os agentes adequados da lista. "
    )
    system_prompt = (
        "És o Diretor de Marketing AI — coordenas copy e criativo na mesma conversa. "
        f"Responde ao utilizador em {language}. "
        f"Agentes disponíveis neste fluxo (usa só estes nomes exatos): {allowed}. "
        f"{scope_rules}"
        f"{linkedin_guidance} "
        "Se faltar objetivo, público ou tom, define needs_clarification=true "
        "e faz no máximo 2 perguntas curtas em reply. "
        "Se já puderes executar, needs_clarification=false e lista team_assignments "
        "com task_brief específico (prioriza Agente Copywriter para o texto). "
        "execution_plan: resumo em 1-3 frases do que vais produzir (copy e, se pedido, imagem). "
        "Responde APENAS com JSON válido: "
        '{"reply":"<mensagem ao utilizador>","needs_clarification":true|false,'
        '"execution_plan":"<plano>","team_assignments":[{"agent_name":"<agente>",'
        '"task_brief":"<tarefa>"}]}'
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0.35,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Histórico da conversa:\n{conversation}\n\n"
                    f"Sugestão automática de agentes (keywords): {keyword_hint}"
                ),
            },
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "reply": raw or "Percebi o pedido. Podes confirmar objetivo e canais?",
            "needs_clarification": True,
            "execution_plan": "",
            "team_assignments": [],
        }

    assignments: List[Dict[str, str]] = []
    catalog_set = set(agent_catalog)
    for item in data.get("team_assignments") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("agent_name", "")).strip()
        brief = str(item.get("task_brief", "")).strip()
        if name in catalog_set and brief:
            assignments.append({"agent_name": name, "task_brief": brief})

    if not assignments and keyword_agents:
        for name in keyword_agents[:MAX_TEAM_AGENTS]:
            assignments.append(
                {
                    "agent_name": name,
                    "task_brief": f"Executar o pedido do utilizador no âmbito de {name}.",
                }
            )

    if not assignments and internal_only and not bool(data.get("needs_clarification", False)):
        assignments.append(
            {
                "agent_name": "Agente Copywriter",
                "task_brief": "Gerar copy de marketing alinhada com o pedido do utilizador.",
            }
        )

    return {
        "reply": str(data.get("reply", "")).strip(),
        "needs_clarification": bool(data.get("needs_clarification", False)),
        "execution_plan": str(data.get("execution_plan", "")).strip(),
        "team_assignments": assignments[:MAX_TEAM_AGENTS],
    }


def _format_copywriter_summary(payload: Dict[str, Any]) -> str:
    """Resume output estruturado do Copywriter para o painel da equipa."""

    parts: List[str] = []
    headlines = payload.get("headlines") or []
    if headlines:
        parts.append("Headlines: " + " | ".join(str(h) for h in headlines[:3]))
    variations = payload.get("main_text_variations") or []
    if variations and isinstance(variations[0], dict):
        parts.append("Copy: " + str(variations[0].get("text", ""))[:400])
    elif payload.get("primary_text"):
        parts.append("Copy: " + str(payload["primary_text"])[:400])
    ctas = payload.get("ctas") or []
    if ctas:
        parts.append("CTAs: " + " | ".join(str(c) for c in ctas[:3]))
    return "\n".join(parts) if parts else "Copy gerada com sucesso."


def _run_specialist_strategy(
    client: OpenAI,
    model: str,
    agent_name: str,
    task_brief: str,
    conversation: str,
    action_steps: Sequence[str],
    language: str,
) -> str:
    """Gera recomendações estratégicas para agentes sem execução automática completa."""

    steps = "\n".join(f"- {s}" for s in action_steps)
    response = client.chat.completions.create(
        model=model,
        temperature=0.45,
        messages=[
            {
                "role": "system",
                "content": (
                    f"És o {agent_name} a trabalhar para o Diretor de Marketing. "
                    f"Responde em {language}, de forma executável (listas curtas). "
                    "Não peças ao utilizador para sair da conversa do Diretor."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Tarefa delegada:\n{task_brief}\n\n"
                    f"Contexto da conversa:\n{conversation}\n\n"
                    f"Plano base da especialidade:\n{steps}"
                ),
            },
        ],
    )
    return (response.choices[0].message.content or "").strip()


def execute_team_assignment(
    agent_name: str,
    task_brief: str,
    conversation: str,
    language: str,
    action_plans: Dict[str, List[str]],
    openai_api_key: str,
    openai_model: str,
) -> Dict[str, Any]:
    """Executa uma tarefa delegada a um membro da equipa.

    Argumentos:
        agent_name: Nome canónico do agente (ex.: `Agente Copywriter`).
        task_brief: Instrução específica que o Diretor delegou.
        conversation: Brief completo da conversa com o utilizador.
        language: Idioma do output.
        action_plans: Planos de ação pré-definidos por agente.
        openai_api_key: Chave OpenAI do servidor.
        openai_model: Modelo a usar nas chamadas LLM.

    Retorno:
        Dicionário com `agent_name`, `status` (`completed`|`skipped`|`error`),
        `summary` (texto para o utilizador) e opcionalmente `error`.
    """

    base = {
        "agent_name": agent_name,
        "status": "completed",
        "summary": "",
        "error": None,
    }
    delegation_user = (
        f"[Delegação do Diretor de Marketing]\n"
        f"Tarefa: {task_brief}\n\n"
        f"Contexto do cliente:\n{conversation}"
    )
    team_messages = [{"role": "user", "content": delegation_user}]

    try:
        if agent_name == COPYWRITER_AGENT:
            if not copywriter_agent.is_configured():
                raise RuntimeError("OPENAI_API_KEY em falta para o Copywriter.")
            brief = f"{task_brief}\n\n---\n{conversation}"
            result = copywriter_agent.generate_marketing_copy(
                brief=brief,
                language=language,
            )
            base["summary"] = _format_copywriter_summary(result)
            return base

        if agent_name == DESIGNER_AGENT:
            if designer_agent.is_configured():
                reply = designer_agent.generate_chat_reply(
                    messages=team_messages,
                    language=language,
                )
            else:
                reply = (
                    "Brief visual registado. Configura credenciais de imagem no servidor "
                    "ou abre o Agente Designer para gerar criativos."
                )
            base["summary"] = reply[:1200]
            return base

        if agent_name in SOCIAL_AGENTS:
            if social_media_agent.is_configured():
                reply = social_media_agent.generate_chat_reply(
                    messages=team_messages,
                    language=language,
                )
            else:
                reply = "Plano de redes sociais pendente — falta OPENAI_API_KEY."
            channel = "Meta/Instagram" if agent_name == "Agente Meta Ads" else "redes sociais"
            base["summary"] = f"[{channel}]\n{reply[:1000]}"
            return base

        if agent_name in LINKEDIN_AGENTS:
            client = OpenAI(api_key=openai_api_key)
            steps = action_plans.get(agent_name, [])
            summary = _run_specialist_strategy(
                client,
                openai_model,
                agent_name,
                task_brief,
                conversation,
                steps,
                language,
            )
            base["summary"] = summary[:1200]
            return base

        client = OpenAI(api_key=openai_api_key)
        steps = action_plans.get(agent_name, ["Executar o pedido com foco em resultado."])
        summary = _run_specialist_strategy(
            client,
            openai_model,
            agent_name,
            task_brief,
            conversation,
            steps,
            language,
        )
        base["summary"] = summary[:1200]
        return base

    except Exception as exc:  # noqa: BLE001
        base["status"] = "error"
        base["error"] = str(exc)
        base["summary"] = f"Não foi possível concluir com {agent_name}: {exc!s}"
        return base


def synthesize_team_response(
    client: OpenAI,
    model: str,
    language: str,
    user_reply_seed: str,
    execution_plan: str,
    task_results: Sequence[Dict[str, Any]],
) -> str:
    """Agrega os outputs da equipa numa única resposta do Diretor.

    Argumentos:
        client: Cliente OpenAI.
        model: Modelo de síntese.
        language: Idioma da resposta final.
        user_reply_seed: Mensagem inicial sugerida pelo plano (opcional).
        execution_plan: Resumo estratégico do plano de equipa.
        task_results: Resultados de `execute_team_assignment` por agente.

    Retorno:
        Texto final do Diretor para mostrar na chatroom.
    """

    blocks: List[str] = []
    for task in task_results:
        name = task.get("agent_name", "Agente")
        status = task.get("status", "completed")
        summary = str(task.get("summary", "")).strip()
        if summary:
            blocks.append(f"### {name} ({status})\n{summary}")

    team_output = "\n\n".join(blocks)
    response = client.chat.completions.create(
        model=model,
        temperature=0.4,
        messages=[
            {
                "role": "system",
                "content": (
                    f"És o Diretor de Marketing AI. Sintetiza o trabalho da tua equipa em {language}. "
                    "Estrutura a resposta com: (1) resumo executivo, (2) entregas por canal/especialista, "
                    "(3) próximos passos concretos. Mantém tom de gestor — profissional e claro. "
                    "Não digas ao utilizador para 'clicar em encaminhar'; ele já está contigo."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Mensagem inicial planeada: {user_reply_seed}\n\n"
                    f"Plano: {execution_plan}\n\n"
                    f"Outputs da equipa:\n{team_output}"
                ),
            },
        ],
    )
    synthesized = (response.choices[0].message.content or "").strip()
    if synthesized:
        return synthesized
    if user_reply_seed:
        return user_reply_seed + "\n\n" + team_output
    return team_output or "A equipa concluiu o pedido. Queres afinar algum canal?"


def build_team_task_payload(
    task_result: Dict[str, Any],
    agent_page_url: Callable[[str], str],
) -> Dict[str, Any]:
    """Formata um resultado de tarefa para a API do Diretor.

    Argumentos:
        task_result: Output de `execute_team_assignment`.
        agent_page_url: Função que mapeia nome do agente → URL da página.

    Retorno:
        Objeto serializável com `agent_name`, `status`, `summary`, `agent_url`.
    """

    agent_name = str(task_result.get("agent_name", ""))
    return {
        "agent_name": agent_name,
        "status": task_result.get("status", "completed"),
        "summary": str(task_result.get("summary", "")).strip(),
        "agent_url": agent_page_url(agent_name),
        "error": task_result.get("error"),
    }
