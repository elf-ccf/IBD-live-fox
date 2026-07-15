from pathlib import Path
import re
import shutil
import subprocess


APP = Path("frontend/src/App.jsx")
ANALYSIS = Path("frontend/src/components/AnalysisPanel.jsx")

if not APP.exists():
    raise RuntimeError("frontend/src/App.jsx not found")


# ------------------------------------------------------------
# 1. Restore AI Output panel if it was hidden/nullified
# ------------------------------------------------------------

if ANALYSIS.exists():
    analysis_text = ANALYSIS.read_text(encoding="utf-8")

    if "return null" in analysis_text and "before-voice-first-hide" in str(list(ANALYSIS.parent.glob("*before-voice-first-hide*"))):
        backups = list(ANALYSIS.parent.glob("AnalysisPanel.jsx.before-voice-first-hide"))
        if backups:
            shutil.copy2(backups[0], ANALYSIS)
            print("Restored AnalysisPanel.jsx from backup.")
    elif "return null" in analysis_text:
        try:
            subprocess.run(
                ["git", "restore", "frontend/src/components/AnalysisPanel.jsx"],
                check=True,
            )
            print("Restored AnalysisPanel.jsx from git.")
        except Exception:
            print("WARNING: AnalysisPanel.jsx still appears hidden. Restore it manually if AI Output is missing.")


# ------------------------------------------------------------
# 2. Move RealtimeFoxLauncher rendering into the Webex area only
# ------------------------------------------------------------

text = APP.read_text(encoding="utf-8")

# Remove old import first.
text = re.sub(
    r'import\s+RealtimeFoxLauncher\s+from\s+["\']\.\/components\/RealtimeFoxLauncher["\'];\n',
    "",
    text,
)

# Remove all existing component usages.
text = re.sub(
    r'\n\s*<RealtimeFoxLauncher\s*[^/]*/>\s*\n',
    "\n",
    text,
)

# Add import after VoiceAssistant import if possible.
import_line = 'import RealtimeFoxLauncher from "./components/RealtimeFoxLauncher";\n'

if import_line not in text:
    marker = 'import VoiceAssistant from "./components/VoiceAssistant";\n'

    if marker in text:
        text = text.replace(marker, marker + import_line, 1)
    else:
        lines = text.splitlines(True)
        insert_at = 0

        for i, line in enumerate(lines):
            if line.startswith("import "):
                insert_at = i + 1

        lines.insert(insert_at, import_line)
        text = "".join(lines)


component = '''
          <RealtimeFoxLauncher />
'''

# Best insertion target: before LIVE CONTEXT area in the Live Webex panel.
if "LIVE CONTEXT" in text:
    index = text.find("LIVE CONTEXT")
    line_start = text.rfind("\n", 0, index)

    text = text[:line_start] + component + text[line_start:]
    print("Inserted RealtimeFoxLauncher before LIVE CONTEXT.")
elif "Connect a Webex meeting" in text:
    index = text.find("Connect a Webex meeting")
    # Insert after the surrounding line, so it stays in Webex section.
    line_end = text.find("\n", index)
    text = text[:line_end + 1] + component + text[line_end + 1:]
    print("Inserted RealtimeFoxLauncher near Connect a Webex meeting.")
elif "Webex meeting URL" in text:
    index = text.find("Webex meeting URL")
    line_end = text.find("\n", index)
    text = text[:line_end + 1] + component + text[line_end + 1:]
    print("Inserted RealtimeFoxLauncher near Webex meeting URL.")
else:
    raise RuntimeError(
        "Could not find Webex section markers. Search App.jsx for the Live Webex panel and insert <RealtimeFoxLauncher /> manually."
    )

APP.write_text(text, encoding="utf-8")

print("Realtime Fox moved to Live Webex section only.")
