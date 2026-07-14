import re
from typing import TypedDict

from langgraph.graph import StateGraph

from app.core.config import settings
from app.schemas.assistant import AssistantAnswer
from app.services.openai_client import get_openai_client


class AgentState(TypedDict):
    """State for the assistant workflow graph."""

    session_id: str
    question: str
    transcript: str
    command_type: str
    web_search_used: bool
    web_research: str
    answer: AssistantAnswer | None
    errors: list[str]


def _needs_extended_details(
    command_type: str,
    question: str,
) -> bool:
    if command_type in {
        "differential",
        "missing_information",
    }:
        return True

    lowered = question.lower()

    return any(
        token in lowered
        for token in [
            "key findings",
            "differential",
            "missing information",
            "limitations",
            "full report",
            "full case",
            "detailed analysis",
        ]
    )


def _strip_boilerplate(text: str) -> str:
    cleaned = text.strip()

    patterns = [
        r"\bthis\s+is\s+ai-generated\b[\s\S]*?([.?!]|$)",
        r"\bthis\s+ai-generated\b[\s\S]*?([.?!]|$)",
        r"\bnot\s+a\s+final\s+diagnosis\b[\s\S]*?([.?!]|$)",
    ]

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalize_answer_shape(
    answer: AssistantAnswer,
    command_type: str,
    question: str,
) -> AssistantAnswer:
    include_extended = _needs_extended_details(
        command_type,
        question,
    )

    answer.answer = _strip_boilerplate(answer.answer)
    answer.audience_script = _strip_boilerplate(
        answer.audience_script
    )

    if not answer.audience_script:
        answer.audience_script = answer.answer

    if not include_extended:
        answer.key_findings = []
        answer.differential = []
        answer.missing_information = []
        answer.limitations = ""
        answer.case_summary = (
            answer.case_summary.strip()[:180]
            if answer.case_summary.strip()
            else ""
        )

    answer.sources = (answer.sources or [])[:3]

    return answer


def classify_command(state: AgentState) -> dict:
    """Classify the user command using deterministic rules."""
    question = state["question"].lower().strip()
    errors = list(state.get("errors", []))

    if any(
        word in question
        for word in [
            "summarize",
            "summary",
            "recap",
            "overview",
        ]
    ):
        command_type = "summarize"
    elif any(
        word in question
        for word in [
            "differential",
            "diagnosis",
            "diagnose",
            "analyze the case",
            "analysis",
        ]
    ):
        command_type = "differential"
    elif any(
        word in question
        for word in [
            "missing",
            "what else",
            "need to know",
            "additional information",
        ]
    ):
        command_type = "missing_information"
    elif question.strip() == "repeat":
        command_type = "repeat"
    else:
        command_type = "general_question"

    return {
        "command_type": command_type,
        "errors": errors,
    }


def research_case(state: AgentState) -> dict:
    """
    Perform default web research via the OpenAI Responses API.

    Always runs. Failure is non-fatal — the answer is still
    generated using the transcript alone.
    """
    errors = list(state.get("errors", []))

    research_prompt = (
        f"A medical education team is discussing the following "
        f"de-identified case transcript:\n\n"
        f"{state['transcript']}\n\n"
        f"The question being addressed is:\n"
        f"{state['question']}\n\n"
        f"Please search for relevant, current, authoritative medical "
        f"information to help answer this educational question. "
        f"Prioritize sources such as PubMed, NCBI, NIH, the American "
        f"College of Gastroenterology, the American Gastroenterological "
        f"Association, the European Crohn's and Colitis Organisation, "
        f"the FDA, and peer-reviewed medical literature. "
        f"Do not use social media, patient blogs, anonymous websites, "
        f"or discussion boards as clinical evidence. "
        f"Do not invent or add patient details not present in the "
        f"transcript. Do not claim a final diagnosis. "
        f"Summarize the most relevant external medical context you find."
    )

    try:
        client = get_openai_client()

        response = client.responses.create(
            model=settings.openai_text_model,
            tools=[
                {
                    "type": "web_search",
                }
            ],
            input=research_prompt,
        )

        web_research = response.output_text or ""

        if web_research.strip():
            return {
                "web_research": web_research,
                "web_search_used": True,
                "errors": errors,
            }

        return {
            "web_research": "",
            "web_search_used": False,
            "errors": errors,
        }

    except Exception as exc:
        errors.append(
            f"Web research warning (non-fatal): {exc}"
        )
        return {
            "web_research": "",
            "web_search_used": False,
            "errors": errors,
        }


def generate_answer(state: AgentState) -> dict:
    """
    Generate a structured AssistantAnswer combining the
    transcript with any available web research.
    """
    errors = list(state.get("errors", []))

    if not state.get("transcript"):
        errors.append("No transcript available.")
        return {
            "answer": None,
            "errors": errors,
        }

    web_section = ""
    if state.get("web_research"):
        web_section = (
            "\n\nExternal Medical Context (from web research):\n"
            + state["web_research"]
        )

    direct_answer_rules = (
        "The user's exact question is the primary task. "
        "Answer that question directly before adding supporting context. "
        "Do not force every response into a meeting summary. "
        "Use the transcript when it is relevant. "
        "Use current web research when it is relevant. "
        "For questions unrelated to the transcript, answer normally using "
        "reliable web research and state that the answer does not depend "
        "on the meeting content. "
        "Clearly separate meeting facts from external information. "
    )

    exact_talking_rules = (
        "CRITICAL STYLE: Answer only the exact question the user asked. "
        "Always use web research, but do not dump extra research details. "
        "Do not generate a full report unless the user specifically asks for one. "
        "Do not include key findings, differential, missing information, or limitations unless explicitly requested. "
        "For normal questions, use empty lists for key_findings, differential, and missing_information. "
        "Keep case_summary empty or one very short context sentence. "
        "Put the complete direct response in the answer field. "
        "The audience_script must be only the direct spoken answer. "
        "Do not start with 'This AI-generated'. "
        "Do not say 'not a final diagnosis' unless the user specifically asks for clinical diagnosis or interpretation. "
        "Do not add disclaimers unless needed. "
        "Keep the audience_script under 45 words. "
        "Use at most 3 sources. "
        "The UI/API already has a separate AI voice disclosure. "
    )

    no_repeated_disclaimer_rules = (
        "Do not include boilerplate disclaimers in answer or audience_script. "
        "Do not say 'This is AI-generated'. "
        "Do not say 'not a final diagnosis' unless the user specifically asks for diagnosis, treatment advice, or clinical decision-making. "
        "For ordinary summary, explanation, latest evidence, or meeting questions, answer directly. "
        "The voice should speak only the direct answer. "
        "The API already contains a separate disclosure field, so do not repeat it in spoken text. "
    )

    developer_instructions = (
        no_repeated_disclaimer_rules +
        exact_talking_rules +
        direct_answer_rules +
        f"You are a medical education assistant for the "
        f"{settings.app_name} system.\n\n"
        f"This is for an IBD (Inflammatory Bowel Disease) medical "
        f"education programme. All cases are simulated or fully "
        f"de-identified educational material.\n\n"
        f"RULES:\n"
        f"1. Treat the transcript as the sole source of patient and "
        f"case facts. Do not add patient details from the internet.\n"
        f"2. Treat web research only as external medical context — "
        f"background evidence, not case-specific facts.\n"
        f"3. Clearly separate what is known from the case transcript "
        f"from what comes from external medical literature.\n"
        f"4. Do NOT claim a final diagnosis. This is educational "
        f"discussion only.\n"
        f"5. Do NOT claim certainty. Use appropriate qualifier language.\n"
        f"6. Do NOT fabricate URLs, citations, dates, quotations, "
        f"studies, recommendations, or guideline text.\n"
        f"7. Only include URLs that actually appear in the provided "
        f"web research context.\n"
        f"8. Clearly identify missing information that would help.\n"
        f"9. State uncertainty and limitations.\n"
        f"10. If available evidence is insufficient, say so.\n"
        f"11. Put all source information only in the sources field.\n"
        f"12. The audience_script must:\n"
        f"    - be concise and suitable for spoken delivery;\n"
        f"    - speak only the direct answer;\n"
        f"    - avoid boilerplate disclaimers unless explicitly requested;\n"
        f"    - NOT read long URLs aloud.\n"
    )

    user_prompt = (
        f"Command type: {state['command_type']}\n\n"
        f"Question: {state['question']}\n\n"
        f"Case Transcript:\n{state['transcript']}"
        f"{web_section}\n\n"
        f"Please provide a structured educational analysis."
    )

    try:
        client = get_openai_client()

        response = client.responses.parse(
            model=settings.openai_text_model,
            input=[
                {
                    "role": "developer",
                    "content": developer_instructions,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            text_format=AssistantAnswer,
        )

        if response.output_parsed is None:
            raise RuntimeError(
                "OpenAI did not return a structured answer."
            )

        normalized_answer = _normalize_answer_shape(
            answer=response.output_parsed,
            command_type=state["command_type"],
            question=state["question"],
        )

        return {
            "answer": normalized_answer,
            "errors": errors,
        }

    except Exception as exc:
        errors.append(f"Answer generation error: {exc}")
        return {
            "answer": None,
            "errors": errors,
        }


def build_assistant_graph() -> StateGraph:
    """Build the three-node assistant workflow graph."""
    graph = StateGraph(AgentState)

    graph.add_node("classify_command", classify_command)
    graph.add_node("research_case", research_case)
    graph.add_node("generate_answer", generate_answer)

    graph.set_entry_point("classify_command")
    graph.add_edge("classify_command", "research_case")
    graph.add_edge("research_case", "generate_answer")
    graph.set_finish_point("generate_answer")

    return graph


# Compile once at module load — not on every request.
ASSISTANT_GRAPH = build_assistant_graph().compile()


def run_assistant_workflow(
    session_id: str,
    question: str,
    transcript: str,
) -> tuple[AssistantAnswer, bool]:
    """
    Run the assistant workflow.

    Returns:
        (AssistantAnswer, web_search_used)

    Raises:
        RuntimeError: If the workflow fails to generate an answer.
    """
    initial_state: AgentState = {
        "session_id": session_id,
        "question": question,
        "transcript": transcript,
        "command_type": "",
        "web_search_used": False,
        "web_research": "",
        "answer": None,
        "errors": [],
    }

    result = ASSISTANT_GRAPH.invoke(initial_state)

    # Non-fatal web search warnings are in errors alongside the answer.
    fatal_errors = [
        e
        for e in result.get("errors", [])
        if not e.startswith("Web research warning")
    ]

    if fatal_errors:
        raise RuntimeError(
            "Workflow error: " + "; ".join(fatal_errors)
        )

    if not result.get("answer"):
        raise RuntimeError("Failed to generate an answer.")

    return result["answer"], result.get("web_search_used", False)
