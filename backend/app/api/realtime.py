import json
import os

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from app.core.config import settings


router = APIRouter(
    prefix="/api/realtime",
    tags=["realtime"],
)


def get_realtime_model():
    return os.getenv(
        "OPENAI_REALTIME_MODEL",
        "gpt-realtime-2.1-mini",
    )


def get_realtime_voice():
    return os.getenv(
        "OPENAI_REALTIME_VOICE",
        "cedar",
    )


def trim_context(value, max_chars=6000):
    value = (value or "").strip()

    if len(value) <= max_chars:
        return value

    return (
        value[:1200].strip()
        + "\n\n[Middle omitted for speed]\n\n"
        + value[-4800:].strip()
    )


async def fetch_session_context(session_id):
    if not session_id:
        return ""

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"http://127.0.0.1:8000/api/sessions/{session_id}/transcript"
            )

        if response.status_code >= 300:
            return ""

        payload = response.json()
        transcript = payload.get("transcript", "")

        if not transcript:
            return ""

        return trim_context(transcript)

    except Exception:
        return ""


def base_instructions():
    return (
        "You are IBD Live Fox, a fast voice-first assistant for simulated or "
        "fully de-identified IBD educational discussions. "
        "Only answer when the user asks a question or says Hey Fox. "
        "Answer only the exact question asked. "
        "Keep spoken answers under 45 words unless the user asks for detail. "
        "Do not create a full case report unless explicitly requested. "
        "Do not add key findings, differential diagnosis, missing information, "
        "or limitations unless explicitly requested. "
        "Do not say AI-generated. "
        "Do not say not a final diagnosis unless the user specifically asks "
        "for diagnosis or treatment advice. "
        "Be concise, natural, and fast."
    )


def build_instructions(context):
    instructions = base_instructions()

    if context:
        instructions += (
            "\n\nUse this meeting transcript context only when it helps answer "
            "the user's exact question. Do not summarize everything unless asked.\n\n"
            "[Meeting context]\n"
            + context
        )

    return instructions


@router.get("/context/{session_id}")
async def realtime_context(session_id: str):
    context = await fetch_session_context(session_id)

    return JSONResponse(
        {
            "session_id": session_id,
            "context": context,
            "context_chars": len(context),
        }
    )


@router.post(
    "/calls",
    response_class=PlainTextResponse,
)
async def create_realtime_call(request: Request):
    sdp_offer = await request.body()

    if not sdp_offer:
        raise HTTPException(
            status_code=400,
            detail="Missing SDP offer body.",
        )

    session_id = (
        request.headers.get("x-meeting-session-id")
        or request.query_params.get("session_id")
        or ""
    )

    context = await fetch_session_context(session_id)

    session_config = {
        "type": "realtime",
        "model": get_realtime_model(),
        "instructions": build_instructions(context),
        "audio": {
            "output": {
                "voice": get_realtime_voice(),
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
    }

    multipart = {
        "sdp": (
            None,
            sdp_offer.decode("utf-8"),
            "application/sdp",
        ),
        "session": (
            None,
            json.dumps(session_config),
            "application/json",
        ),
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/realtime/calls",
            headers=headers,
            files=multipart,
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
    return HTMLResponse(
        """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>IBD Live Fox Realtime</title>
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
        width: min(760px, 92vw);
        padding: 32px;
        border-radius: 24px;
        background: rgba(24, 24, 32, 0.94);
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

      label {
        display: block;
        margin-top: 18px;
        color: #c4c4cf;
        font-size: 13px;
        font-weight: 800;
      }

      input {
        width: 100%;
        margin-top: 8px;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.16);
        background: rgba(255,255,255,0.06);
        color: white;
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

      button.secondary {
        margin-left: 10px;
        background: rgba(255,255,255,0.08);
      }

      .status {
        margin-top: 18px;
        color: #a78bfa;
        font-weight: 800;
      }

      .debug {
        margin-top: 16px;
        padding: 12px;
        border-radius: 12px;
        background: rgba(255,255,255,0.05);
        color: #b8b8c5;
        font-size: 13px;
        white-space: pre-wrap;
        max-height: 180px;
        overflow: auto;
      }

      audio {
        width: 100%;
        margin-top: 18px;
      }
    </style>
  </head>

  <body>
    <main class="card">
      <h1>IBD Live Fox Realtime</h1>

      <p>
        Fast audio-first Fox using OpenAI Realtime. Add a meeting session ID
        if you want Fox to use transcript context, then connect and speak.
      </p>

      <label for="sessionId">Meeting session ID, optional</label>
      <input id="sessionId" placeholder="Optional session_id for transcript context" />

      <button id="connect">
        Connect Realtime Fox
      </button>

      <button id="loadContext" class="secondary">
        Check context
      </button>

      <div id="status" class="status">
        Not connected
      </div>

      <audio id="remoteAudio" autoplay controls></audio>

      <div id="debug" class="debug">Debug events will show here.</div>
    </main>

    <script>
      const connectButton = document.getElementById("connect");
      const loadContextButton = document.getElementById("loadContext");
      const statusEl = document.getElementById("status");
      const debugEl = document.getElementById("debug");
      const remoteAudio = document.getElementById("remoteAudio");
      const sessionInput = document.getElementById("sessionId");

      const params = new URLSearchParams(window.location.search);
      const sessionFromUrl = params.get("session_id") || "";

      if (sessionFromUrl) {
        sessionInput.value = sessionFromUrl;
      }

      let pc = null;

      function setStatus(message) {
        statusEl.textContent = message;
      }

      function debug(message, data) {
        const line = data
          ? `${message}: ${JSON.stringify(data).slice(0, 700)}`
          : message;

        debugEl.textContent = line + "\\n" + debugEl.textContent;
      }

      async function checkContext() {
        const sessionId = sessionInput.value.trim();

        if (!sessionId) {
          setStatus("No session ID provided.");
          return;
        }

        const response = await fetch(`/api/realtime/context/${sessionId}`);
        const data = await response.json();

        debug("Context check", data);
        setStatus(`Context loaded: ${data.context_chars || 0} chars`);
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

        pc.oniceconnectionstatechange = () => {
          debug("ICE state", pc.iceConnectionState);
        };

        const dataChannel = pc.createDataChannel("oai-events");

        dataChannel.onopen = () => {
          setStatus("Realtime connected. Say: Hey Fox...");
          debug("Data channel open");
        };

        dataChannel.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.type) {
              debug(data.type, data);
            }
          } catch {
            debug("Realtime raw event", event.data);
          }
        };

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const sessionId = sessionInput.value.trim();

        setStatus("Connecting to OpenAI Realtime...");

        const response = await fetch(
          `/api/realtime/calls${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/sdp",
              "x-meeting-session-id": sessionId,
            },
            body: offer.sdp,
          }
        );

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
          setStatus("Error: " + error.message);
          debug("Connection error", {
            message: error.message,
          });
          pc = null;
        }
      });

      loadContextButton.addEventListener("click", async () => {
        try {
          await checkContext();
        } catch (error) {
          setStatus("Context error: " + error.message);
          debug("Context error", {
            message: error.message,
          });
        }
      });
    </script>
  </body>
</html>
        """
    )


@router.get(
    "/webex-agent",
    response_class=HTMLResponse,
)
async def realtime_webex_agent():
    """
    Recall.ai Output Media page.

    This page auto-connects to OpenAI Realtime when loaded by the Recall bot.
    It is intended for the Live Webex mode.
    """

    return HTMLResponse(
        """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>IBD Live Fox Webex Agent</title>

    <style>
      html,
      body {
        width: 100%;
        height: 100%;
        margin: 0;
        background: #09090b;
        color: white;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        overflow: hidden;
      }

      .stage {
        display: grid;
        width: 100%;
        height: 100%;
        place-items: center;
        text-align: center;
      }

      .card {
        width: min(760px, 88vw);
        padding: 48px;
        border-radius: 32px;
        background: rgba(20, 20, 28, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.14);
        box-shadow: 0 30px 90px rgba(0, 0, 0, 0.38);
      }

      .orb {
        width: 96px;
        height: 96px;
        margin: 0 auto 24px;
        border-radius: 30px;
        background: linear-gradient(145deg, #a78bfa, #8b5cf6, #fb7185);
        animation: pulse 1.2s ease-in-out infinite;
      }

      h1 {
        margin: 0;
        font-size: 46px;
        letter-spacing: -0.04em;
      }

      p {
        margin: 14px 0 0;
        color: #b8b8c5;
        font-size: 19px;
      }

      .status {
        margin-top: 24px;
        color: #a78bfa;
        font-size: 16px;
        font-weight: 900;
      }

      .hint {
        margin-top: 16px;
        color: #8f8fa3;
        font-size: 14px;
      }

      audio {
        width: 100%;
        margin-top: 24px;
      }

      @keyframes pulse {
        50% {
          transform: scale(1.06);
          box-shadow: 0 0 0 22px rgba(139, 92, 246, 0.08);
        }
      }
    </style>
  </head>

  <body>
    <main class="stage">
      <section class="card">
        <div class="orb"></div>

        <h1>IBD Live Fox</h1>

        <p>Realtime Webex voice assistant</p>

        <div id="status" class="status">
          Starting...
        </div>

        <div class="hint">
          Say: Hey Fox, summarize what we are discussing.
        </div>

        <audio id="remoteAudio" autoplay></audio>
      </section>
    </main>

    <script>
      const statusEl = document.getElementById("status");
      const remoteAudio = document.getElementById("remoteAudio");

      const params = new URLSearchParams(window.location.search);
      const sessionId = params.get("session_id") || "";

      let pc = null;

      function setStatus(message) {
        statusEl.textContent = message;
      }

      async function connect() {
        try {
          setStatus("Requesting meeting audio...");

          const mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
          });

          pc = new RTCPeerConnection();

          mediaStream.getTracks().forEach((track) => {
            pc.addTrack(track, mediaStream);
          });

          pc.ontrack = (event) => {
            remoteAudio.srcObject = event.streams[0];

            remoteAudio.play().catch(() => {
              setStatus("Connected. Audio playback pending.");
            });

            setStatus("Listening for Hey Fox");
          };

          pc.oniceconnectionstatechange = () => {
            if (pc.iceConnectionState === "connected") {
              setStatus("Listening for Hey Fox");
            }

            if (
              pc.iceConnectionState === "failed" ||
              pc.iceConnectionState === "disconnected"
            ) {
              setStatus("Realtime connection interrupted");
            }
          };

          const dataChannel = pc.createDataChannel("oai-events");

          dataChannel.onopen = () => {
            setStatus("Listening for Hey Fox");
          };

          dataChannel.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);

              if (
                data.type &&
                (
                  data.type.includes("response.audio") ||
                  data.type.includes("output_audio")
                )
              ) {
                setStatus("Speaking");
              }

              if (
                data.type === "response.done" ||
                data.type === "response.completed"
              ) {
                setStatus("Listening for Hey Fox");
              }
            } catch {
              // Ignore noisy debug events.
            }
          };

          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);

          setStatus("Connecting Realtime Fox...");

          const route = sessionId
            ? `/api/realtime/calls?session_id=${encodeURIComponent(sessionId)}`
            : "/api/realtime/calls";

          const response = await fetch(route, {
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

          await pc.setRemoteDescription({
            type: "answer",
            sdp: answerSdp,
          });

          setStatus("Listening for Hey Fox");
        } catch (error) {
          console.error(error);
          setStatus("Realtime error: " + error.message);
        }
      }

      connect();
    </script>
  </body>
</html>
        """
    )


@router.post("/webex")
async def create_realtime_webex_agent(request: Request):
    """
    Create the normal Recall Webex bot, then immediately start Output Media
    with the OpenAI Realtime agent page.
    """

    body = await request.json()

    public_base_url = settings.public_base_url.strip().rstrip("/")

    if not public_base_url.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="PUBLIC_BASE_URL must use public HTTPS for Recall Output Media.",
        )

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
        timeout=60,
    ) as client:
        recall_response = await client.post(
            "/api/recall/webex",
            json=body,
        )

    if recall_response.status_code >= 300:
        raise HTTPException(
            status_code=recall_response.status_code,
            detail=recall_response.text,
        )

    result = recall_response.json()

    session_id = result.get("session_id")
    bot_id = result.get("recall_bot_id") or result.get("bot_id")

    if not session_id or not bot_id:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Recall bot was created but session_id or recall_bot_id was missing.",
                "result": result,
            },
        )

    output_page_url = (
        f"{public_base_url}/api/realtime/webex-agent"
        f"?session_id={session_id}"
    )

    recall_base = settings.recall_region_base_url.strip().rstrip("/")

    output_media_payload = {
        "camera": {
            "kind": "webpage",
            "config": {
                "url": output_page_url,
            },
        },
    }

    headers = {
        "Authorization": f"Token {settings.recall_api_key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        output_response = await client.post(
            f"{recall_base}/api/v1/bot/{bot_id}/output_media/",
            headers=headers,
            json=output_media_payload,
        )

    result["realtime_output_media_url"] = output_page_url
    result["realtime_output_media_status"] = output_response.status_code

    if output_response.status_code >= 300:
        result["realtime_output_media_error"] = output_response.text

    return result
