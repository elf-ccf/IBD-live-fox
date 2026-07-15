import asyncio
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

import httpx
import websockets
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from websockets.legacy.client import connect

from app.core.config import settings


router = APIRouter(
  prefix="/api/webex-realtime",
  tags=["webex-realtime"],
)


logger = logging.getLogger(__name__)

LOG_DIR = Path("/tmp/ibd-live-webex-realtime")
LOG_DIR.mkdir(parents=True, exist_ok=True)

AGENT_CLIENT_JS = (
  Path(__file__).resolve().parents[1]
  / "webex_agent"
  / "agent_client.js"
)

WAKE_PHRASES = (
  "hey fox",
  "hi fox",
  "okay fox",
  "ok fox",
  "hey folks",
  "hey box",
)


def public_base_url():
  return settings.public_base_url.strip().rstrip("/")


def to_public_wss(https_base_url: str) -> str:
  if not https_base_url.startswith("https://"):
    raise ValueError("PUBLIC_BASE_URL must start with https://")

  return "wss://" + https_base_url[len("https://") :]


def recall_base_url():
  return settings.recall_region_base_url.strip().rstrip("/")


def recall_headers():
  return {
    "Authorization": f"Token {settings.recall_api_key.strip()}",
    "Accept": "application/json",
    "Content-Type": "application/json",
  }


def openai_realtime_model():
  return settings.openai_realtime_model


def openai_realtime_voice():
  return settings.openai_realtime_voice


def wake_gate_enabled() -> bool:
  value = os.getenv("WEBEX_WAKE_GATE_ENABLED", "false").strip().lower()
  return value in {"1", "true", "yes", "on"}


def openai_realtime_url() -> str:
  return f"wss://api.openai.com/v1/realtime?model={openai_realtime_model()}"


def webex_system_instructions() -> str:
  return (
    "You are IBD Live Fox. "
    "Stay silent unless a participant clearly addresses you with Hey Fox. "
    "Also tolerate Hi Fox, Okay Fox, OK Fox, Hey folks, and Hey box. "
    "Do not answer ordinary meeting conversation. "
    "When addressed, answer only the command after the wake phrase. "
    "Keep answers under 45 words unless more detail is requested. "
    "After answering once, return to silent listening. "
    "Do not repeatedly introduce yourself. "
    "Do not create a full case report unless explicitly requested. "
    "Do not add unrelated sections. "
    "Speak naturally and concisely."
  )


def webex_session_update_payload() -> dict:
  gate_enabled = wake_gate_enabled()

  session = {
    "type": "realtime",
    "instructions": webex_system_instructions(),
    "audio": {
      "input": {
        "format": {
          "type": "audio/pcm",
          "rate": 24000,
        },
        "turn_detection": {
          "type": "server_vad",
          "threshold": 0.5,
          "prefix_padding_ms": 300,
          "silence_duration_ms": 700,
          "create_response": not gate_enabled,
        },
      },
      "output": {
        "format": {
          "type": "audio/pcm",
          "rate": 24000,
        },
        "voice": openai_realtime_voice(),
      },
    },
  }

  if gate_enabled:
    session["audio"]["input"]["transcription"] = {
      "model": os.getenv(
        "OPENAI_REALTIME_TRANSCRIPTION_MODEL",
        "gpt-4o-mini-transcribe",
      )
    }

  return {
    "type": "session.update",
    "session": session,
  }


def write_log(session_id: str, message: str) -> None:
  session_name = session_id or "unknown-session"
  log_path = LOG_DIR / f"{session_name}.log"

  with log_path.open("a", encoding="utf-8") as handle:
    handle.write(message.rstrip() + "\n")


def summarize_event(event: dict) -> str:
  event_type = str(event.get("type", ""))

  if event_type in {"input_audio_buffer.append", "response.output_audio.delta", "response.audio.delta"}:
    key = "audio" if "audio" in event else "delta"
    payload_size = len(str(event.get(key, "")))
    return f"{event_type} payload_chars={payload_size}"

  if event_type == "error":
    message = (
      event.get("error", {})
      .get("message", "")
      .strip()
    )
    return f"error message={message[:180]}"

  if event_type.startswith("response") or event_type.startswith("conversation"):
    return event_type

  return event_type or "unknown"


def extract_transcript_text(event: dict) -> str:
  transcript = str(event.get("transcript") or "").strip()

  if transcript:
    return transcript

  item = event.get("item")

  if isinstance(item, dict):
    content = item.get("content")

    if isinstance(content, list):
      for part in content:
        if isinstance(part, dict):
          text = str(part.get("transcript") or part.get("text") or "").strip()
          if text:
            return text

  return ""


def extract_wake_command(text: str) -> str | None:
  lowered = " ".join(text.lower().replace("-", " ").split())

  for wake_phrase in WAKE_PHRASES:
    index = lowered.find(wake_phrase)

    if index < 0:
      continue

    command = text[index + len(wake_phrase) :].lstrip(" ,.:;!?-").strip()

    if command:
      return command

  return None


@router.get("/health")
async def webex_realtime_health():
  return {
    "status": "ok",
    "service": "webex-realtime-v2",
    "public_base_url": public_base_url(),
    "openai_realtime_model": openai_realtime_model(),
    "openai_realtime_voice": openai_realtime_voice(),
    "wake_gate_enabled": wake_gate_enabled(),
  }


@router.get("/agent", response_class=HTMLResponse)
async def webex_realtime_agent():
  return HTMLResponse(
    """
<!doctype html>
<html>
  <head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>IBD Live Fox</title>
  <style>
    html,
    body {
    margin: 0;
    width: 100%;
    height: 100%;
    background: radial-gradient(circle at 20% 20%, #1f2937, #09090b 60%);
    color: #ffffff;
    font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    overflow: hidden;
    }

    .stage {
    width: 100%;
    height: 100%;
    display: grid;
    place-items: center;
    }

    .card {
    width: min(760px, 88vw);
    border-radius: 28px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(15, 23, 42, 0.86);
    padding: 38px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
    }

    .brand {
    display: flex;
    align-items: center;
    gap: 14px;
    }

    .dot {
    width: 22px;
    height: 22px;
    border-radius: 999px;
    background: #ef4444;
    }

    .dot.connecting {
    background: #f59e0b;
    animation: pulse 1.2s infinite;
    }

    .dot.connected,
    .dot.listening {
    background: #10b981;
    }

    .dot.speaking {
    background: #38bdf8;
    animation: pulse 0.8s infinite;
    }

    .dot.error {
    background: #ef4444;
    }

    h1 {
    margin: 0;
    font-size: 42px;
    letter-spacing: -0.02em;
    }

    p {
    margin: 10px 0 0;
    color: #c9d1d9;
    font-size: 18px;
    }

    #status {
    margin-top: 16px;
    font-size: 20px;
    font-weight: 700;
    color: #a5b4fc;
    }

    #debug {
    margin-top: 16px;
    padding: 12px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.06);
    color: #a8b3cf;
    font-size: 12px;
    line-height: 1.45;
    max-height: 220px;
    overflow: hidden;
    white-space: pre-wrap;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }

    @keyframes pulse {
    50% {
      transform: scale(1.12);
      opacity: 0.7;
    }
    }
  </style>
  </head>
  <body>
  <main class="stage">
    <section class="card">
    <div class="brand">
      <div id="dot" class="dot"></div>
      <h1>IBD Live Fox</h1>
    </div>
    <p>Cisco Webex Realtime audio bridge</p>
    <div id="status">Connecting</div>
    <div id="debug">booting...</div>
    </section>
  </main>
  <script type="module" src="/api/webex-realtime/agent-client.js"></script>
  </body>
</html>
    """
  )


@router.get("/agent-client.js")
async def webex_realtime_agent_client():
  return FileResponse(
    AGENT_CLIENT_JS,
    media_type="application/javascript",
  )


@router.websocket("/ws")
async def webex_realtime_ws(websocket: WebSocket):
  session_id = websocket.query_params.get("session_id", "")
  offered_subprotocol = websocket.headers.get("sec-websocket-protocol", "")
  selected_subprotocol = "realtime" if "realtime" in offered_subprotocol.lower() else None

  await websocket.accept(subprotocol=selected_subprotocol)

  openai_ws = None
  gate_waiting_for_response = False

  write_log(session_id, "[ws.open] browser connected")
  logger.info("WEBEX relay client connected session=%s", session_id or "none")

  try:
    openai_ws = await connect(
      openai_realtime_url(),
      extra_headers={
        "Authorization": f"Bearer {settings.openai_api_key}",
      },
      subprotocols=["realtime"],
      max_size=16 * 1024 * 1024,
    )

    first_message = await openai_ws.recv()
    first_event = json.loads(first_message)

    if first_event.get("type") != "session.created":
      raise RuntimeError(
        f"Expected session.created but received {first_event.get('type')}"
      )

    await openai_ws.send(json.dumps(webex_session_update_payload()))
    await websocket.send_text(json.dumps(first_event))

    write_log(session_id, "[openai] session.created")
    logger.info(
      "WEBEX relay connected OpenAI model=%s voice=%s",
      openai_realtime_model(),
      openai_realtime_voice(),
    )

    async def browser_to_openai():
      async for message in websocket.iter_text():
        try:
          event = json.loads(message)
        except json.JSONDecodeError:
          write_log(session_id, "[browser] invalid json")
          continue

        event_type = str(event.get("type", ""))

        if event_type == "session.update":
          event = webex_session_update_payload()
          event_type = "session.update"

        if event_type == "input_audio_buffer.append":
          write_log(session_id, "[browser->openai] input_audio_buffer.append")
        elif event_type:
          write_log(session_id, f"[browser->openai] {event_type}")

        await openai_ws.send(json.dumps(event))

    async def openai_to_browser():
      nonlocal gate_waiting_for_response

      async for message in openai_ws:
        try:
          event = json.loads(message)
        except json.JSONDecodeError:
          write_log(session_id, "[openai] invalid json")
          continue

        event_type = str(event.get("type", ""))
        summary = summarize_event(event)

        if event_type != "response.output_audio.delta":
          write_log(session_id, f"[openai->browser] {summary}")

        if event_type == "error":
          logger.error("WEBEX relay OpenAI error: %s", summary)

        if wake_gate_enabled():
          transcript_types = {
            "conversation.item.input_audio_transcription.completed",
            "input_audio_buffer.transcript.final",
            "input_audio_transcript.completed",
          }

          if event_type in transcript_types and not gate_waiting_for_response:
            transcript = extract_transcript_text(event)
            command = extract_wake_command(transcript)

            if command:
              gate_waiting_for_response = True

              await openai_ws.send(
                json.dumps(
                  {
                    "type": "response.create",
                    "response": {
                      "instructions": (
                        "Answer the following wake command only: "
                        f"{command}"
                      )
                    },
                  }
                )
              )

              logger.info("WEBEX wake gate accepted command")
              write_log(session_id, "[wake-gate] command accepted")
            elif transcript:
              write_log(session_id, "[wake-gate] ignored non-wake transcript")

          if event_type == "response.done":
            gate_waiting_for_response = False

        await websocket.send_text(json.dumps(event))

    await asyncio.gather(browser_to_openai(), openai_to_browser())

  except WebSocketDisconnect:
    write_log(session_id, "[ws.close] browser disconnected")

  except websockets.exceptions.ConnectionClosed as error:
    logger.info(
      "WEBEX relay closed code=%s reason=%s",
      error.code,
      error.reason,
    )

  except Exception as error:
    logger.exception("WEBEX relay error: %s", error)

    try:
      await websocket.send_text(
        json.dumps(
          {
            "type": "error",
            "error": {
              "message": str(error)[:240],
            },
          }
        )
      )
    except Exception:
      pass

  finally:
    if openai_ws and not openai_ws.closed:
      await openai_ws.close(code=1000, reason="browser disconnected")

    try:
      await websocket.close()
    except Exception:
      pass

    write_log(session_id, "[ws.finally] relay closed")


@router.get("/logs/{session_id}")
async def webex_realtime_logs(session_id: str):
  log_path = LOG_DIR / f"{session_id}.log"

  if not log_path.exists():
    return {
      "session_id": session_id,
      "logs": "",
      "exists": False,
    }

  return {
    "session_id": session_id,
    "logs": log_path.read_text(encoding="utf-8")[-12000:],
    "exists": True,
  }


@router.post("/start")
async def start_webex_realtime(request: Request):
  body = await request.json()

  base = public_base_url()

  if not base.startswith("https://"):
    raise HTTPException(
      status_code=400,
      detail="PUBLIC_BASE_URL must be a public HTTPS URL for Recall/Webex.",
    )

  relay_wss_url = f"{to_public_wss(base)}/api/webex-realtime/ws"

  recall_request = dict(body)
  recall_request["bot_name"] = "IBD Live Fox"

  async with httpx.AsyncClient(
    base_url="http://127.0.0.1:8000",
    timeout=60,
  ) as client:
    recall_response = await client.post(
      "/api/recall/webex",
      json=recall_request,
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
        "message": "Missing session_id or recall_bot_id from Recall bot response.",
        "result": result,
      },
    )

  agent_url = (
    f"{base}/api/webex-realtime/agent"
    f"?wss={quote(relay_wss_url, safe='')}"
    f"&session_id={quote(str(session_id), safe='')}"
    f"&bot_id={quote(str(bot_id), safe='')}"
    f"&t={int(time.time())}"
  )

  output_payload = {
    "camera": {
      "kind": "webpage",
      "config": {
        "url": agent_url,
      },
    },
  }

  async with httpx.AsyncClient(timeout=60) as client:
    output_response = await client.post(
      f"{recall_base_url()}/api/v1/bot/{bot_id}/output_media/",
      headers=recall_headers(),
      json=output_payload,
    )

  result["bot_name"] = "IBD Live Fox"
  result["webex_realtime_agent_url"] = agent_url
  result["webex_realtime_relay_wss"] = relay_wss_url
  result["webex_realtime_output_media_status"] = output_response.status_code

  if output_response.status_code >= 300:
    result["webex_realtime_output_media_error"] = output_response.text

  write_log(
    str(session_id),
    json.dumps(
      {
        "type": "start",
        "session_id": session_id,
        "bot_id": bot_id,
        "agent_url": agent_url,
        "relay_wss": relay_wss_url,
        "output_media_status": output_response.status_code,
      },
      ensure_ascii=False,
    ),
  )

  return JSONResponse(result)
