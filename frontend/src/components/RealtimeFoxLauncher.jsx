import React, { useEffect, useRef, useState } from "react";
import { Radio } from "lucide-react";
import { storeFoxResponse } from "../lib/api";


function getBackendUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL;

  if (configured) {
    return configured.replace(/\/$/, "");
  }

  return "";
}


export default function RealtimeFoxLauncher({
  activeSessionId = "",
  mode = "transcript",
  transcriptionPending = false,
}) {
  const backendUrl = getBackendUrl();

  const peerRef = useRef(null);
  const streamRef = useRef(null);
  const channelRef = useRef(null);
  const audioRef = useRef(null);
  const connectAbortRef = useRef(null);
  const connectCanceledRef = useRef(false);
  const storedResponseIdsRef = useRef(
    new Set()
  );

  const [voiceState, setVoiceState] = useState("disconnected");
  const [connectedSessionId, setConnectedSessionId] = useState("");

  const connecting = voiceState === "connecting";
  const connected = voiceState === "listening" || voiceState === "speaking";
  const isSpeaking = voiceState === "speaking";
  const isError = voiceState === "error";

  const hasSession = Boolean(activeSessionId);
  const reconnectRequired = Boolean(
    connected && connectedSessionId && activeSessionId && connectedSessionId !== activeSessionId
  );

  const disabledReason = transcriptionPending
    ? "Transcribing recording..."
    : mode === "webex"
      ? "Wait for live meeting speech first"
      : "Add a transcript or recording first";

  function buttonLabel() {
    if (voiceState === "connecting") {
      return "Connecting...";
    }

    if (voiceState === "speaking") {
      return "Speaking";
    }

    if (voiceState === "listening") {
      return "Listening";
    }

    if (voiceState === "error") {
      return "Retry Fox";
    }

    return "Ask Fox";
  }

  async function cleanupConnection(resetSession = false) {
    connectCanceledRef.current = true;

    if (connectAbortRef.current) {
      connectAbortRef.current.abort();
      connectAbortRef.current = null;
    }

    try {
      channelRef.current?.close();
    } catch {
      // Ignore close noise.
    }

    try {
      peerRef.current?.close();
    } catch {
      // Ignore close noise.
    }

    try {
      streamRef.current?.getTracks()?.forEach((track) => track.stop());
    } catch {
      // Ignore stop noise.
    }

    channelRef.current = null;
    peerRef.current = null;
    streamRef.current = null;

    if (audioRef.current) {
      audioRef.current.srcObject = null;
    }

    if (resetSession) {
      setConnectedSessionId("");
    }
  }

  async function disconnectRealtime() {
    await cleanupConnection(false);
    setVoiceState("disconnected");
  }

  async function connectRealtime() {
    if (reconnectRequired) {
      setVoiceState("error");
      await disconnectRealtime();
      return;
    }

    if (peerRef.current || connecting) {
      return;
    }

    connectCanceledRef.current = false;
    setVoiceState("connecting");

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      if (connectCanceledRef.current) {
        mediaStream.getTracks().forEach((track) => track.stop());
        return;
      }

      streamRef.current = mediaStream;

      const peer = new RTCPeerConnection();
      peerRef.current = peer;

      mediaStream.getTracks().forEach((track) => {
        peer.addTrack(track, mediaStream);
      });

      peer.ontrack = (event) => {
        if (!audioRef.current) {
          return;
        }

        audioRef.current.srcObject = event.streams[0];
        audioRef.current.play().catch(() => {
          // Autoplay may still be restricted in some browsers.
        });
      };

      const dataChannel = peer.createDataChannel("oai-events");
      channelRef.current = dataChannel;

      dataChannel.onopen = () => {
        setVoiceState("listening");
      };

      dataChannel.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const eventType = String(
            payload?.type || ""
          );

          if (
            eventType.includes("response.audio") ||
            eventType.includes("output_audio")
          ) {
            setVoiceState("speaking");
          }

          if (
            eventType ===
              "response.output_audio_transcript.done" ||
            eventType ===
              "response.audio_transcript.done"
          ) {
            const responseText = String(
              payload?.transcript || ""
            ).trim();

            const responseId = String(
              payload?.response_id ||
              payload?.item_id ||
              payload?.event_id ||
              ""
            ).trim();

            if (
              responseText &&
              responseId &&
              activeSessionId &&
              !storedResponseIdsRef.current.has(
                responseId
              )
            ) {
              storedResponseIdsRef.current.add(
                responseId
              );

              void storeFoxResponse({
                sessionId: activeSessionId,
                responseId,
                text: responseText,
              }).catch((storageError) => {
                storedResponseIdsRef.current.delete(
                  responseId
                );

                console.warn(
                  "Unable to store Fox response:",
                  storageError
                );
              });
            }
          }

          if (
            eventType === "response.done" ||
            eventType === "response.completed"
          ) {
            setVoiceState("listening");
          }
        } catch {
          // Ignore noisy realtime events.
        }
      };

      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);

      const abortController = new AbortController();
      connectAbortRef.current = abortController;

      const route = `/api/realtime/calls?session_id=${encodeURIComponent(activeSessionId)}&mode=analysis`;

      const response = await fetch(`${backendUrl}${route}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/sdp",
          "x-meeting-session-id": activeSessionId,
        },
        body: offer.sdp,
        signal: abortController.signal,
      });

      connectAbortRef.current = null;

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const answerSdp = await response.text();
      await peer.setRemoteDescription({
        type: "answer",
        sdp: answerSdp,
      });

      setConnectedSessionId(activeSessionId);
      setVoiceState("listening");
    } catch (error) {
      await cleanupConnection(false);

      if (error?.name === "AbortError") {
        setVoiceState("disconnected");
      } else {
        setVoiceState("error");
      }
    } finally {
      connectAbortRef.current = null;
      connectCanceledRef.current = false;
    }
  }

  useEffect(() => {
    if (!hasSession) {
      setConnectedSessionId("");
    }
  }, [hasSession]);

  useEffect(() => {
    if (!hasSession || transcriptionPending) {
      void cleanupConnection(true);
      setVoiceState("disconnected");
    } else if (connectedSessionId && activeSessionId && connectedSessionId !== activeSessionId) {
      setVoiceState("error");
    }
  }, [hasSession, transcriptionPending, mode, connectedSessionId, activeSessionId]);

  useEffect(() => {
    return () => {
      void cleanupConnection(true);
    };
  }, []);

  const canInteract = hasSession && !transcriptionPending;

  return (
    <>
      <button
        type="button"
        className={[
          "realtime-fox-fab",
          connecting ? "connecting" : "",
          connected ? "connected" : "",
          isSpeaking ? "speaking" : "",
          isError ? "error" : "",
        ].join(" ").trim()}
        aria-label="Ask Fox"
        title={canInteract ? "Ask Fox" : disabledReason}
        disabled={!canInteract}
        onClick={() => {
          if (connecting) {
            void cleanupConnection(false);
            setVoiceState("disconnected");
            return;
          }

          if (connected) {
            void disconnectRealtime();
            return;
          }

          void connectRealtime();
        }}
      >
        <span className="realtime-fox-fab-dot" data-connected={connected ? "true" : "false"} />
        {connecting && <span className="realtime-fox-spinner" aria-hidden="true" />}
        {!connecting && <Radio size={16} />}
        <span>{buttonLabel()}</span>
      </button>

      <audio
        ref={audioRef}
        autoPlay
        playsInline
        className="realtime-fox-audio-hidden"
      />
    </>
  );
}
