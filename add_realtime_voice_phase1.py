from pathlib import Path
import re


# ------------------------------------------------------------
# 1. Add backend realtime router
# ------------------------------------------------------------

realtime_api = Path("backend/app/api/realtime.py")

realtime_api.write_text(
r'''import json
import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.core.config import settings


router = APIRouter(
    prefix="/api/realtime",
    tags=["realtime"],
)


def get_realtime_model() -> str:
    return os.getenv(
        "OPENAI_REALTIME_MODEL",
        "gpt-realtime-2.1-mini",
    )


def get_realtime_voice() -> str:
    return os.getenv(
        "OPENAI_REALTIME_VOICE",
        "cedar",
    )


def get_realtime_instructions() -> str:
    return (
        "You are IBD Live Fox, a voice-first assistant for simulated or "
        "fully de-identified IBD educational discussions. "
        "Respond only when the user asks a question or says Hey Fox. "
        "Answer only the exact question asked. "
        "Keep spoken answers under 45 words unless the user asks for detail. "
        "Do not create a full case report unless explicitly requested. "
        "Do not say AI-generated. "
        "Do not say not a final diagnosis unless the user specifically asks "
        "for diagnosis or treatment advice. "
        "Be concise, natural, and fast."
    )


@router.post(
    "/calls",
    response_class=PlainTextResponse,
)
async def create_realtime_call(request: Request):
    """
    Browser sends SDP offer here.
    Backend forwards offer to OpenAI Realtime Calls API.
    Backend returns SDP answer.
    """

    sdp_offer = await request.body()

    if not sdp_offer:
        raise HTTPException(
            status_code=400,
            detail="Missing SDP offer body.",
        )

    session_config = {
        "type": "realtime",
        "model": get_realtime_model(),
        "instructions": get_realtime_instructions(),
        "audio": {
            "output": {
                "voice": get_realtime_voice(),
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
    }

    files = {
        "sdp": (
            "offer.sdp",
            sdp_offer,
            "application/sdp",
        ),
        "session": (
            None,
            json.dumps(session_config),
        ),
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/realtime/calls",
            headers=headers,
            files=files,
        )

    if response.status_code >= 300:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text,
        )

    return PlainTextResponse(
        response.text,
        media_type="application/sdp",
    )


@router.get(
    "/test-page",
    response_class=HTMLResponse,
)
async def realtime_test_page():
    """
    Simple standalone test page for OpenAI Realtime voice.

    Open:
      http://127.0.0.1:8000/api/realtime/test-page

    Click Connect, allow microphone, then speak.
    """

    return HTMLResponse(
        """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>IBD Live Fox Realtime Test</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #09090b;
        color: white;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      .card {
        width: min(720px, 90vw);
        padding: 32px;
        border-radius: 24px;
        background: rgba(24, 24, 32, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.14);
      }

      h1 {
        margin: 0 0 12px;
        font-size: 34px;
      }

      p {
        color: #c4c4cf;
        line-height: 1.6;
      }

      button {
        margin-top: 18px;
        padding: 14px 20px;
        border: 0;
        border-radius: 999px;
        color: white;
        background: linear-gradient(135deg, #8b5cf6, #fb7185);
        font-weight: 800;
        cursor: pointer;
      }

      .status {
        margin-top: 18px;
        color: #a78bfa;
        font-weight: 800;
      }

      audio {
        width: 100%;
        margin-top: 18px;
      }
    </style>
  </head>
  <body>
    <main class="card">
      <h1>IBD Live Fox Realtime Test</h1>
      <p>
        Click connect, allow the microphone, then say:
        <strong>Hey Fox, summarize this discussion.</strong>
      </p>

      <button id="connect">
        Connect Realtime Voice
      </button>

      <div id="status" class="status">
        Not connected
      </div>

      <audio id="remoteAudio" autoplay controls></audio>
    </main>

    <script>
      const connectButton = document.getElementById("connect");
      const statusEl = document.getElementById("status");
      const remoteAudio = document.getElementById("remoteAudio");

      let pc = null;

      function setStatus(message) {
        statusEl.textContent = message;
      }

      async function connectRealtime() {
        if (pc) {
          setStatus("Already connected");
          return;
        }

        setStatus("Requesting microphone...");

        const mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

        pc = new RTCPeerConnection();

        mediaStream.getTracks().forEach((track) => {
          pc.addTrack(track, mediaStream);
        });

        pc.ontrack = (event) => {
          remoteAudio.srcObject = event.streams[0];
          setStatus("Connected. Fox is listening.");
        };

        const dataChannel = pc.createDataChannel("oai-events");

        dataChannel.onopen = () => {
          setStatus("Realtime connected. Speak naturally.");
        };

        dataChannel.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type) {
              console.log("Realtime event:", data.type, data);
            }
          } catch {
            console.log("Realtime raw event:", event.data);
          }
        };

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        setStatus("Connecting to OpenAI Realtime...");

        const response = await fetch("/api/realtime/calls", {
          method: "POST",
          headers: {
            "Content-Type": "application/sdp",
          },
          body: offer.sdp,
        });

        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail);
        }

        const answerSdp = await response.text();

        await pc.setRemoteDescription({
          type: "answer",
          sdp: answerSdp,
        });

        setStatus("Connected. Say: Hey Fox...");
      }

      connectButton.addEventListener("click", async () => {
        try {
          await connectRealtime();
        } catch (error) {
          console.error(error);
          setStatus(`Error: ${error.message}`);
          pc = null;
        }
      });
    </script>
  </body>
</html>
        """
    )
''',
encoding="utf-8",
)


# ------------------------------------------------------------
# 2. Include router in backend/main.py
# ------------------------------------------------------------

main_path = Path("backend/main.py")

if not main_path.exists():
    raise RuntimeError("backend/main.py not found")

main = main_path.read_text(encoding="utf-8")

import_line = "from app.api.realtime import router as realtime_router\n"
include_line = "app.include_router(realtime_router)\n"

if import_line not in main:
    lines = main.splitlines(True)
    insert_at = 0

    for index, line in enumerate(lines):
        if line.startswith("from app.api.") or line.startswith("from fastapi") or line.startswith("import "):
            insert_at = index + 1

    lines.insert(insert_at, import_line)
    main = "".join(lines)

if include_line not in main:
    # Place after other include_router calls if possible.
    matches = list(re.finditer(r"app\.include_router\(.*?\)\n", main))

    if matches:
  *     insert_at = matches[-1].end()*        main = main[:insert_at] + *nclude_line + main[insert_at:]
   *else:
        main = main.rstrip()*+ "\n\n" + include_line + "\n"

ma*n_path.write_text(main, encoding="*tf-8")

print("Added OpenAI Realti*e phase 1 endpoint and test page."*
