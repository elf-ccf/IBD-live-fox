from pathlib import Path
import re
import shutil


FILES = [
    Path("backend/app/workflows/assistant_graph.py"),
    Path("backend/app/api/assistant.py"),
    Path("backend/app/services/live_assistant.py"),
]

for path in FILES:
    if path.exists():
        shutil.copy2(
            path,
            path.with_suffix(path.suffix + ".before-exact-question-fast-audio")
        )


# ------------------------------------------------------------
# 1. Backend prompt: exact question only, no extra report
# ------------------------------------------------------------

graph = Path("backend/app/workflows/assistant_graph.py")

if not graph.exists():
    raise RuntimeError("assistant_graph.py not found")

text = graph.read_text(encoding="utf-8")

text = (
    text
    .replace("&gt;", ">")
    .replace("&lt;", "<")
    .replace("&amp;", "&")
)

rules = '''    exact_question_fast_audio_rules = (
        "CRITICAL BEHAVIOR: Answer only the exact question the user asked. "
        "Do not create a case report unless the user explicitly asks for a case report. "
        "Do not add key findings, differential diagnosis, missing information, limitations, or teaching sections unless explicitly requested. "
        "For normal questions, use empty lists for key_findings, differential, and missing_information. "
        "Keep limitations empty unless the user asks for clinical decision-making. "
        "Keep case_summary empty or one very short context sentence. "
        "If web search is available, search only for information directly needed to answer the user's exact question. "
        "Do not search for broad background information or unrelated topics. "
        "Use at most 3 strong sources and only include sources that directly support the answer. "
        "The answer field must contain the complete direct answer. "
        "The audience_script must be the same direct answer in a natural spoken form. "
        "Do not say 'This is AI-generated'. "
        "Do not say 'not a final diagnosis' unless the user specifically asks for diagnosis or treatment advice. "
        "Do not add disclaimers to ordinary summaries or meeting questions. "
        "Keep the spoken answer under 45 words unless the user asks for detail. "
    )

'''

if "exact_question_fast_audio_rules =" not in text:
    marker = "    developer_instructions = ("

    if marker not in text:
        raise RuntimeError("developer_instructions block not found")

    text = text.replace(
        marker,
        rules + marker,
        1,
    )

    text = text.replace(
        "    developer_instructions = (\n",
        "    developer_instructions = (\n"
        "        exact_question_fast_audio_rules +\n",
        1,
    )

graph.write_text(text, encoding="utf-8")


# ------------------------------------------------------------
# 2. Speech should use direct answer, not audience_script
# ------------------------------------------------------------

for file_name in [
    "backend/app/api/assistant.py",
    "backend/app/services/live_assistant.py",
]:
    path = Path(file_name)

    if not path.exists():
        continue

    content = path.read_text(encoding="utf-8")

    content = content.replace(
        "generate_speech(answer.audience_script)",
        "generate_speech(answer.answer)",
    )

    content = content.replace(
        "generate_speech(\n            answer.audience_script\n        )",
        "generate_speech(\n            answer.answer\n        )",
    )

    content = content.replace(
        "generate_speech(\n                answer.audience_script\n            )",
        "generate_speech(\n                answer.answer\n            )",
    )

    path.write_text(content, encoding="utf-8")


# ------------------------------------------------------------
# 3. Make sure obvious boilerplate is not hardcoded anywhere
# ------------------------------------------------------------

for path in FILES:
    if not path.exists():
        continue

    content = path.read_text(encoding="utf-8")

    content = content.replace(
        "This AI-generated summary",
        "",
    )

    content = content.replace(
        "This AI-generated response",
        "",
    )

    content = content.replace(
        "This is AI-generated",
        "",
    )

    content = content.replace(
        "not a final diagnosis",
        "",
    )

    path.write_text(content, encoding="utf-8")


print("Exact-question fast audio mode applied.")
