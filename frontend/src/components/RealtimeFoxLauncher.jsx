import React from "react";
import { ExternalLink, Radio } from "lucide-react";


function getBackendUrl() {
  const configured =
    import.meta.env.VITE_API_BASE_URL;

  if (configured) {
    return configured.replace(/\/$/, "");
  }

  const { protocol, hostname } = window.location;

  if (
    hostname.includes(".app.github.dev") &&
    hostname.includes("-5173.")
  ) {
    return `${protocol}//${hostname.replace("-5173.", "-8000.")}`;
  }

  return "http://127.0.0.1:8000";
}


export default function RealtimeFoxLauncher() {
  function openRealtimeFox() {
    const backendUrl = getBackendUrl();

    window.open(
      `${backendUrl}/api/realtime/test-page`,
      "_blank",
      "noopener,noreferrer"
    );
  }

  return (
    <section className="workspace-card realtime-fox-card">
      <header className="card-header">
        <div>
          <div className="section-eyebrow">
            REALTIME VOICE
          </div>

          <h2>
            <Radio size={21} />
            Realtime Fox
          </h2>
        </div>
      </header>

      <p className="realtime-fox-copy">
        Fast audio-first Fox using OpenAI Realtime. Use this for quicker,
        more natural spoken responses.
      </p>

      <button
        type="button"
        className="primary-button"
        onClick={openRealtimeFox}
      >
        <ExternalLink size={17} />
        Open Realtime Fox
      </button>
    </section>
  );
}
