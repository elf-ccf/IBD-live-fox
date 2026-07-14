from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.config import settings


router = APIRouter(
    prefix="/api/recall",
    tags=["recall-output"],
)


def html_tag(name, body="", attrs=None):
    attrs = attrs or {}
    lt = chr(60)
    gt = chr(62)

    attr_text = ""

    for key, value in attrs.items():
        html_key = key.replace("_", "-")

        if value is True:
            attr_text += f" {html_key}"
        elif value is not False and value is not None:
            attr_text += f' {html_key}="{value}"'

    return f"{lt}{name}{attr_text}{gt}{body}{lt}/{name}{gt}"


def render_page(status_text, body_extra=""):
    style = """
html, body {
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
  width: min(720px, 86vw);
  padding: 48px;
  background: rgba(20, 20, 28, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 32px;
}

.orb {
  width: 90px;
  height: 90px;
  margin: 0 auto 24px;
  border-radius: 28px;
  background: linear-gradient(145deg, #a78bfa, #8b5cf6, #fb7185);
  animation: pulse 1.2s ease-in-out infinite;
}

h1 {
  margin: 0;
  font-size: 42px;
}

p {
  margin: 14px 0 0;
  color: #b8b8c5;
  font-size: 18px;
}

.status {
  margin-top: 20px;
  color: #a78bfa;
  font-size: 15px;
  font-weight: 800;
}

.hidden-audio {
  display: none;
}

@keyframes pulse {
  50% {
    transform: scale(1.06);
    box-shadow: 0 0 0 18px rgba(139, 92, 246, 0.08);
  }
}
"""

    card_body = (
        html_tag("div", "", {"class": "orb"})
        + html_tag("h1", "IBD Live Fox")
        + html_tag("p", "Meeting assistant")
        + html_tag(
            "div",
            status_text,
            {
                "id": "status",
                "class": "status",
            },
        )
        + body_extra
    )

    head = html_tag(
        "head",
        '<meta charset="utf-8" />'
        + '<meta name="viewport" content="width=device-width, initial-scale=1" />'
        + html_tag("title", "IBD Live Fox")
        + html_tag("style", style),
    )

    body = html_tag(
        "body",
        html_tag(
            "div",
            html_tag(
                "div",
                card_body,
                {
                    "class": "card",
                },
            ),
            {
                "class": "stage",
            },
        ),
    )

    return "<!doctype html>" + html_tag("html", head + body)


@router.get(
    "/idle-player",
    response_class=HTMLResponse,
)
async def idle_player():
    return HTMLResponse(
        render_page("Listening for Hey Fox...")
    )


@router.get(
    "/output-player/{file_name}",
    response_class=HTMLResponse,
)
async def output_player(file_name):
    if "/" in file_name or "\\" in file_name:
        return HTMLResponse(
            "<h1>Invalid audio file</h1>",
            status_code=400,
        )

    if not file_name.endswith(".mp3"):
        return HTMLResponse(
            "<h1>Only MP3 is supported</h1>",
            status_code=400,
        )

    base_url = settings.public_base_url.strip().rstrip("/")
    audio_url = f"{base_url}/api/audio/{file_name}"

    audio = html_tag(
        "audio",
        "Audio playback unavailable.",
        {
            "id": "fox-audio",
            "src": audio_url,
            "autoplay": True,
            "preload": "auto",
            "playsinline": True,
            "class": "hidden-audio",
        },
    )

    script = """
<script>
  const audio = document.getElementById("fox-audio");
  const status = document.getElementById("status");

  let hasStarted = false;
  let hasFinished = false;

  function setStatus(message) {
    status.textContent = message;
  }

  async function playOnce() {
    if (!audio || hasStarted || hasFinished) {
      return;
    }

    try {
      hasStarted = true;
      audio.currentTime = 0;
      audio.volume = 1.0;
      audio.muted = false;
      await audio.play();
      setStatus("Speaking now");
    } catch (error) {
      hasStarted = false;
      setStatus("Retrying playback...");
      setTimeout(playOnce, 700);
    }
  }

  audio.addEventListener("loadstart", function () {
    setStatus("Loading response...");
  });

  audio.addEventListener("loadedmetadata", function () {
    setStatus("Response loaded");
    playOnce();
  });

  audio.addEventListener("canplay", function () {
    playOnce();
  });

  audio.addEventListener("playing", function () {
    setStatus("Speaking now");
  });

  audio.addEventListener("ended", function () {
    hasFinished = true;
    audio.pause();
    audio.muted = true;
    setStatus("Listening for Hey Fox...");
  });

  audio.addEventListener("error", function () {
    setStatus("Audio failed to load");
  });

  setTimeout(playOnce, 500);
  setTimeout(playOnce, 1500);
</script>
"""

    return HTMLResponse(
        render_page(
            "Loading response...",
            audio + script,
        )
    )
