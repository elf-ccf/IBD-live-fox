from pathlib import Path
import re


APP = Path("frontend/src/App.jsx")
FOX = Path("frontend/src/components/RealtimeFoxLauncher.jsx")
CSS = Path("frontend/src/modern.css")


# ------------------------------------------------------------
# 1. Rewrite RealtimeFoxLauncher.jsx cleanly
# ------------------------------------------------------------

FOX.write_text(
r'''import React, { useRef, useState } from "react";
import { Mic, MicOff, Radio, Volume2 } from "lucide-react";


function getBackendUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL;

  if (configured) {
    return configured.replace(/\/$/, "");
  }

  return "";
}


function getSessionId(session) {
  return (
    session?.id ||
    session?.session_id ||
    session?.meeting_session_id ||
    ""
  );
}


function getSessionDate(session) {
  return (
    session?.updated_at ||
    session?.created_at ||
    session?.started_at ||
    ""
  );
}


async function getTranscriptInfo(backendUrl, sessionId) {
  try {
    const response = await fetch(
      `${backendUrl}/api/sessions/${sessionId}/transcript`
    );

    if (!response.ok) {
      return {
        sessionId,
        segmentCount: 0,
        transcriptLength: 0,
      };
    }

    const data = await response.json();

    return {
      sessionId,
      segmentCount: data.segment_count || data.segments?.length || 0,
      transcriptLength: data.transcript?.length || 0,
    };
  } catch {
    return {
      sessionId,
      segmentCount: 0,
      transcriptLength: 0,
    };
  }
}


async function findBestSessionWithTranscript(backendUrl) {
  try {
    const response = await fetch(`${backendUrl}/api/sessions`);

    if (!response.ok) {
      return null;
    }

    const payload = await response.json();

    const sessions = Array.isArray(payload)
      ? payload
      : payload.sessions || payload.items || payload.data || [];

    if (!Array.isArray(sessions) || sessions.length === 0) {
      return null;
    }

    const sorted = [...sessions].sort((a, b) => {
      const aDate = new Date(getSessionDate(a)).getTime() || 0;
      const bDate = new Date(getSessionDate(b)).getTime() || 0;

      return bDate - aDate;
    });

    const recent = sorted.slice(0, 8);
    const checked = [];

    for (const session of recent) {
      const sessionId = getSessionId(session);

      if (!sessionId) {
        continue;
      }

      const info = await getTranscriptInfo(backendUrl, sessionId);

      checked.push({
        ...info,
        title: session.title || session.name || "Untitled session",
      });
    }

    const withTranscript = checked
      .filter((item) => item.segmentCount > 0 || item.transcriptLength > 0)
      .sort((a, b) => {
        if (b.segmentCount !== a.segmentCount) {
          return b.segmentCount - a.segmentCount;
        }

        return b.transcriptLength - a.transcriptLength;
      });

    return withTranscript[0] || checked[0] || null;
  } catch {
    return null;
  }
}


export default function RealtimeFoxLauncher() {
  const peerRef = useRef(null);
  const streamRef = useRef(null);
  const audioRef = useRef(null);

  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [status, setStatus] = useState("Ready for Webex voice");
  const [sessionInfo, setSessionInfo] = useState(null);


  async function connectRealtime() {
    if (peerRef.current || connecting) {
      return;
    }

    const backendUrl = getBackendUrl();

    setConnecting(true);
    setStatus("Finding Webex context...");

    try {
      const bestSession = await findBestSessionWithTranscript(backendUrl);

      setSessionInfo(bestSession);

      setStatus("Requesting microphone...");

      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      streamRef.current = mediaStream;

      const peer = new RTCPeerConnection();

      peerRef.current = peer;

      mediaStream.getTracks().forEach((track) => {
        peer.addTrack(track, mediaStream);
      });

      peer.ontrack = (event) => {
        if (audioRef.current) {
          audioRef.current.srcObject = event.streams[0];

          audioRef.current.play().catch(() => {
            setStatus("Connected. Select Play if browser blocks audio.");
          });
        }

        setStatus("Listening for Hey Fox");
      };

      const dataChannel = peer.createDataChannel("oai-events");

      dataChannel.onopen = () => {
        setStatus("Listening for Hey Fox");
      };

      dataChannel.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (
            data?.type?.includes("response.audio") ||
            data?.type?.includes("output_audio")
          ) {
            setStatus("Speaking");
          }

          if (
            data?.type === "response.done" ||
            data?.type === "response.completed"
          ) {
            setStatus("Listening for Hey Fox");
          }
        } catch {
          // Ignore noisy realtime events.
        }
      };

      const offer = await peer.createOffer();

      await peer.setLocalDescription(offer);

      const sessionId = bestSession?.sessionId || "";

      const route = sessionId
        ? `/api/realtime/calls?session_id=${encodeURIComponent(sessionId)}`
        : "/api/realtime/calls";

      setStatus("Connecting to Realtime voice...");

      const response = await fetch(`${backendUrl}${route}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/sdp",
          "x-meeting-session-id": sessionId,
        },
        body: offer.sdp,
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail);
      }

      const answerSdp = await response.text();

      await peer.setRemoteDescription({
        type: "answer",
        sdp: answerSdp,
      });

      setConnected(true);
      setStatus("Listening for Hey Fox");
    } catch (error) {
      console.error(error);
      setStatus(`Error: ${error.message}`);
      disconnectRealtime();
    } finally {
      setConnecting(false);
    }
  }


  function disconnectRealtime() {
    try {
      peerRef.current?.close();
    } catch {
      // Ignore.
    }

    try {
      streamRef.current?.getTracks()?.forEach((track) => track.stop());
    } catch {
      // Ignore.
    }

    peerRef.current = null;
    streamRef.current = null;

    if (audioRef.current) {
      audioRef.current.srcObject = null;
    }

    setConnected(false);
    setConnecting(false);
    setStatus("Ready for Webex voice");
  }


  return (
    <section className="webex-realtime-fox">
      <div className="webex-realtime-icon">
        <Radio size={18} />
      </div>

      <div className="webex-realtime-main">
        <div className="webex-realtime-header">
          <div>
            <p className="webex-realtime-kicker">
              LIVE WEBEX VOICE
            </p>

            <h3>
              Realtime Fox
            </h3>
          </div>

          <span className={connected ? "fox-live-dot is-live" : "fox-live-dot"}>
            {connected ? "Live" : "Idle"}
          </span>
        </div>

        <p className="webex-realtime-copy">
          Use this only for live Webex voice. Transcript and recording analysis
          still use the AI Output panel.
        </p>

        <div className="webex-realtime-controls">
          {!connected ? (
            <button
              type="button"
              className="primary-button compact-button"
              onClick={connectRealtime}
              disabled={connecting}
            >
              <Mic size={16} />
              {connecting ? "Connecting..." : "Connect voice"}
            </button>
          ) : (
            <button
              type="button"
              className="secondary-button compact-button"
              onClick={disconnectRealtime}
            >
              <MicOff size={16} />
              Disconnect
            </button>
          )}

          <div className="webex-realtime-status">
            <Volume2 size={15} />
            <span>{status}</span>
          </div>
        </div>

        {sessionInfo?.sessionId && (
          <p className="webex-realtime-context">
            Context: {sessionInfo.segmentCount} segments loaded
          </p>
        )}

        <audio
          ref={audioRef}
          autoPlay
          controls
          className="webex-realtime-audio"
        />
      </div>
    </section>
  );
}
''',
encoding="utf-8",
)


# ------------------------------------------------------------
# 2. Repair App.jsx import and placement
# ------------------------------------------------------------

text = APP.read_text(encoding="utf-8")

# Remove corrupted/duplicate import lines wherever they landed.
text = re.sub(
    r'^\s*import\s+RealtimeFoxLauncher\s+from\s+["\']\.\/components\/RealtimeFoxLauncher["\'];\s*\n',
    "",
    text,
    flags=re.MULTILINE,
)

# Remove all existing Realtime component usages and wrappers.
text = re.sub(
    r'\n\s*<RealtimeFoxLauncher\s*/>\s*\n',
    "\n",
    text,
)

text = re.sub(
    r'\n\s*<div\s+className=["\']webex-realtime-slot["\']>\s*<RealtimeFoxLauncher\s*/>\s*</div>\s*\n',
    "\n",
    text,
    flags=re.DOTALL,
)

# Insert import after the initial import section, respecting multi-line imports.
lines = text.splitlines(True)
insert_at = 0
inside_import = False

for index, line in enumerate(lines):
    stripped = line.strip()

    if index == 0 and stripped.startswith("import "):
        inside_import = not stripped.endswith(";")
        insert_at = index + 1
        continue

    if inside_import:
        insert_at = index + 1
        if stripped.endswith(";"):
            inside_import = False
        continue

    if stripped.startswith("import "):
        inside_import = not stripped.endswith(";")
        insert_at = index + 1
        continue

    if stripped == "":
        insert_at = index + 1
        continue

    break

lines.insert(
    insert_at,
    'import RealtimeFoxLauncher from "./components/RealtimeFoxLauncher";\n',
)

text = "".join(lines)

component = '''
          <div className="webex-realtime-slot">
            <RealtimeFoxLauncher />
          </div>
'''

# Insert exactly once after the Send AI to Webex button.
marker = "Send AI to Webex"

if marker in text:
    marker_index = text.find(marker)
    button_end = text.find("</button>", marker_index)

    if button_end != -1:
        line_end = text.find("\n", button_end)

        if line_end == -1:
            line_end = button_end + len("</button>")

        text = text[:line_end + 1] + component + text[line_end + 1:]
    else:
        raise RuntimeError("Found Send AI to Webex but could not find closing button.")
else:
    marker = "LIVE CONTEXT"

    if marker not in text:
        raise RuntimeError("Could not find Webex insertion marker.")

    marker_index = text.find(marker)
    line_start = text.rfind("\n", 0, marker_index)
    text = text[:line_start] + component + text[line_start:]

APP.write_text(text, encoding="utf-8")


# ------------------------------------------------------------
# 3. Clean obvious corrupted CSS paste fragments and append clean CSS
# ------------------------------------------------------------

css = CSS.read_text(encoding="utf-8")

bad_fragments = [
    "CSS;",
    "CSSargin",
    "tiary);;",
    "197, 94, 0.12);2);185);ba",
]

for frag in bad_fragments:
    css = css.replace(frag, "")

# Remove previous Webex-only block if it exists, so we avoid duplicates.
css = re.sub(
    r'/\* Webex-only Realtime Fox \*/[\s\S]*?(?=/\*|$)',
    "",
    css,
)

css += r'''

/* Webex-only Realtime Fox */

.webex-realtime-slot {
  margin: 16px 0;
}

.webex-realtime-fox {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  align-items: start;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(139, 92, 246, 0.24);
  background:
    linear-gradient(135deg, rgba(139, 92, 246, 0.12), rgba(251, 113, 133, 0.08)),
    rgba(255, 255, 255, 0.035);
}

.webex-realtime-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 14px;
  color: #fff;
  background: linear-gradient(135deg, #8b5cf6, #fb7185);
  box-shadow: 0 12px 30px rgba(139, 92, 246, 0.22);
}

.webex-realtime-main {
  min-width: 0;
}

.webex-realtime-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.webex-realtime-kicker {
  margin: 0 0 3px;
  color: var(--text-tertiary);
  font-size: 0.68rem;
  font-weight: 900;
  letter-spacing: 0.1em;
}

.webex-realtime-header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1rem;
}

.fox-live-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border-radius: 999px;
  color: var(--text-secondary);
  background: rgba(255,255,255,0.06);
  font-size: 0.72rem;
  font-weight: 800;
  white-space: nowrap;
}

.fox-live-dot::before {
  content: "";
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #94a3b8;
}

.fox-live-dot.is-live {
  color: #bbf7d0;
  background: rgba(34, 197, 94, 0.12);
}

.fox-live-dot.is-live::before {
  background: #22c55e;
  box-shadow: 0 0 0 5px rgba(34, 197, 94, 0.12);
}

.webex-realtime-copy {
  margin: 8px 0 12px;
  color: var(--text-secondary);
  font-size: 0.86rem;
  line-height: 1.5;
}

.webex-realtime-controls {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.compact-button {
  min-height: 38px;
  padding: 10px 14px;
}

.webex-realtime-status {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 700;
}

.webex-realtime-context {
  margin: 9px 0 0;
  color: var(--text-tertiary);
  font-size: 0.76rem;
}

.webex-realtime-audio {
  width: 100%;
  margin-top: 12px;
}
'''

CSS.write_text(css, encoding="utf-8")

print("Repaired Webex-only Realtime Fox UI.")
