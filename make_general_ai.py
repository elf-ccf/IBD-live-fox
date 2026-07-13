from pathlib import Path
import shutil


ROOT = Path("/workspaces/ibd-live/ibd-live-ai")

APP_FILE = ROOT / "frontend/src/App.jsx"
ANALYSIS_FILE = ROOT / "frontend/src/components/AnalysisPanel.jsx"
GRAPH_FILE = ROOT / "backend/app/workflows/assistant_graph.py"


def backup(path: Path) -> None:
    backup_path = path.with_suffix(
        path.suffix + ".before-general-ai"
    )

    shutil.copy2(path, backup_path)

    print(f"Backup: {backup_path}")


def require_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"File not found: {path}")


for file_path in [
    APP_FILE,
    ANALYSIS_FILE,
    GRAPH_FILE,
]:
    require_file(file_path)
    backup(file_path)


# ---------------------------------------------------------
# Frontend: make the question input general-purpose
# ---------------------------------------------------------

app_text = APP_FILE.read_text(encoding="utf-8")

old_question_patterns = [
    '''const [question, setQuestion] = useState(
    "Summarize the presentation for the panel."
  );''',
    '''const [question, setQuestion] =
    useState(
      "Summarize the presentation for the panel."
    );''',
]

question_changed = False

for old_pattern in old_question_patterns:
    if old_pattern in app_text:
        app_text = app_text.replace(
            old_pattern,
            '''const [question, setQuestion] =
    useState("");''',
            1,
        )

        question_changed = True
        break

if not question_changed:
    print(
        "Notice: Default question pattern was not found. "
        "It may already be empty."
    )


placeholder_patterns = [
    'placeholder="Ask about the presentation…"',
    'placeholder="Ask about the presentation..."',
]

for old_placeholder in placeholder_patterns:
    if old_placeholder in app_text:
        app_text = app_text.replace(
            old_placeholder,
            'placeholder="Ask anything using the meeting content and current web information…"',
        )


app_text = app_text.replace(
    "Ask and speak",
    "Ask AI",
)


# Replace quick-command configuration when detectable.
quick_start = "const QUICK_COMMANDS = ["
quick_end = "];"

if quick_start in app_text:
    before, remainder = app_text.split(
        quick_start,
        1,
    )

    if quick_end in remainder:
        _, after = remainder.split(
            quick_end,
            1,
        )

        new_quick_commands = '''const QUICK_COMMANDS = [
  {
    label: "Ask about this case",
    prompt:
      "What are the most important insights from this presentation?",
  },
  {
    label: "Current evidence",
    prompt:
      "Search current reliable sources for information relevant to this presentation and explain the findings.",
  },
  {
    label: "Latest guidance",
    prompt:
      "What is the latest authoritative guidance relevant to the topic discussed in this presentation?",
  },
  {
    label: "Educational differential",
    prompt:
      "Provide an educational differential analysis grounded in the presentation and current reliable information.",
  },
  {
    label: "Missing information",
    prompt:
      "What important information is missing before this case can be interpreted more confidently?",
  },
];'''

        app_text = (
            before
            + new_quick_commands
            + after
        )

        print("Updated quick questions.")
    else:
        print(
            "Notice: Could not find the end of "
            "QUICK_COMMANDS."
        )
else:
    print(
        "Notice: QUICK_COMMANDS was not found."
    )


APP_FILE.write_text(
    app_text,
    encoding="utf-8",
)

print("Updated frontend question experience.")


# ---------------------------------------------------------
# Backend: make the exact user question the primary task
# ---------------------------------------------------------

graph_text = GRAPH_FILE.read_text(
    encoding="utf-8"
)

general_ai_rules = """
PRIMARY TASK RULES:

1. The user's exact question is the primary task.
2. Answer the exact question directly before giving supporting context.
3. Do not summarize the presentation unless:
   - the user explicitly requests a summary; or
   - a short presentation summary is necessary to answer the question.
4. The transcript is optional context, not the only topic the user may ask about.
5. For questions about current facts, recent publications, guidelines,
   organizations, products, treatments, research, news, or other
   time-sensitive information, use the supplied web research.
6. For a general question unrelated to the transcript, answer using reliable
   external research and clearly state that the response does not depend on
   the meeting transcript.
7. Clearly separate presentation facts from internet information.
8. Do not invent patient facts, citations, dates, URLs, quotations, study
   results, or recommendations.
"""


if "PRIMARY TASK RULES:" not in graph_text:
    prompt_markers = [
        '''instructions = """''',
        '''system_prompt = f"""''',
        '''system_prompt = """''',
    ]

    inserted = False

    for marker in prompt_markers:
        if marker in graph_text:
            graph_text = graph_text.replace(
                marker,
                marker + general_ai_rules,
                1,
            )

            inserted = True
            break

    if not inserted:
        print(
            "Warning: Main assistant instructions "
            "were not found automatically."
        )
else:
    print(
        "Primary-task rules already exist."
    )


# Strengthen the web research prompt if one exists.
research_marker = 'research_prompt = f"""'

if research_marker in graph_text:
    research_rules = """
The user's exact question is the primary research task.

Determine what current internet information is useful for answering that
question. Do not force the response into a meeting summary.

The user may ask:
- a question about the meeting;
- a current medical or scientific question;
- a general factual question;
- a question combining meeting context and internet research.

Search reliable and authoritative sources when current or external
information would improve the answer.

"""

    if (
        "The user's exact question is the primary research task."
        not in graph_text
    ):
        graph_text = graph_text.replace(
            research_marker,
            research_marker + research_rules,
            1,
        )

        print("Updated automatic web research instructions.")
else:
    print(
        "Warning: research_prompt was not found. "
        "Check that the graph still has a research node."
    )


# Make the final user prompt explicitly prioritize the question.
user_prompt_markers = [
    'user_prompt = f"""',
    'user_message = f"""',
]

for marker in user_prompt_markers:
    if marker in graph_text:
        direct_answer_instruction = """
Answer the user's exact question first.

Use the meeting content when relevant.
Use current web research when relevant.
Do not force the answer into a case summary when the user asked something
different.

"""

        if (
            "Do not force the answer into a case summary"
            not in graph_text
        ):
            graph_text = graph_text.replace(
                marker,
                marker + direct_answer_instruction,
                1,
            )

        break


GRAPH_FILE.write_text(
    graph_text,
    encoding="utf-8",
)

print("Updated LangGraph instructions.")


# ---------------------------------------------------------
# Frontend result label: present the answer as the main output
# ---------------------------------------------------------

analysis_text = ANALYSIS_FILE.read_text(
    encoding="utf-8"
)

analysis_text = analysis_text.replace(
    "<h3>Response</h3>",
    "<h3>AI answer</h3>",
)

analysis_text = analysis_text.replace(
    "<h3>Answer</h3>",
    "<h3>AI answer</h3>",
)

analysis_text = analysis_text.replace(
    "<h3>Case summary</h3>",
    "<h3>Presentation context</h3>",
)

ANALYSIS_FILE.write_text(
    analysis_text,
    encoding="utf-8",
)

print("Updated analysis labels.")
print()
print("Patch completed.")
