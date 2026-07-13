import {
  LoaderCircle,
  Mic,
  MicOff,
  Volume2,
} from "lucide-react";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";


const WAKE_PHRASE = "hey ai";


function extractCommand(text) {
  const original = text.trim();
  const lower = original.toLowerCase();
  const position = lower.indexOf(WAKE_PHRASE);

  if (position < 0) {
    return null;
  }

  const command = original
    .slice(position + WAKE_PHRASE.length)
    .replace(/^[\s,.:;!?—-]+/, "")
    .trim();

  return command || null;
}


export default function VoiceAssistant({
  onCommand,
  disabled = false,
  busy = false,
  speaking = false,
}) {
  const recognitionRef = useRef(null);
  const enabledRef = useRef(false);
  const mountedRef = useRef(true);
  const commandRunningRef = useRef(false);

  const [supported, setSupported] =
    useState(true);

  const [enabled, setEnabled] =
    useState(false);

  const [listening, setListening] =
    useState(false);

  const [transcript, setTranscript] =
    useState("");

  const [detectedCommand, setDetectedCommand] =
    useState("");

  const [error, setError] = useState("");


  const canListen =
    enabled &&
    !disabled &&
    !busy &&
    !speaking &&
    !commandRunningRef.current;


  const startRecognition = useCallback(() => {
    if (
      !recognitionRef.current ||
      !enabledRef.current ||
      disabled ||
      busy ||
      speaking ||
      commandRunningRef.current
    ) {
      return;
    }

    try {
      recognitionRef.current.start();
    } catch {
      // Recognition is probably already active.
    }
  }, [disabled, busy, speaking]);


  const stopRecognition = useCallback(
    (abort = false) => {
      if (!recognitionRef.current) {
        return;
      }

      try {
        if (abort) {
          recognitionRef.current.abort();
        } else {
          recognitionRef.current.stop();
        }
      } catch {
        // Recognition is already stopped.
      }
    },
    []
  );


  const activateVoice = useCallback(() => {
    setError("");
    setEnabled(true);
    enabledRef.current = true;

    window.setTimeout(
      startRecognition,
      150
    );
  }, [startRecognition]);


  const deactivateVoice = useCallback(() => {
    enabledRef.current = false;
    setEnabled(false);
    setListening(false);
    setTranscript("");
    stopRecognition(true);
  }, [stopRecognition]);


  useEffect(() => {
    mountedRef.current = true;

    const Recognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    if (!Recognition) {
      setSupported(false);
      return undefined;
    }

    const recognition = new Recognition();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      if (!mountedRef.current) {
        return;
      }

      setListening(true);
      setError("");
    };

    recognition.onresult = async (event) => {
      let visibleText = "";
      let finalText = "";

      for (
        let index = event.resultIndex;
        index < event.results.length;
        index += 1
      ) {
        const result = event.results[index];
        const spokenText =
          result[0]?.transcript || "";

        visibleText += `${spokenText} `;

        if (result.isFinal) {
          finalText += `${spokenText} `;
        }
      }

      const displayed = visibleText.trim();

      if (displayed) {
        setTranscript(displayed);
      }

      if (!finalText.trim()) {
        return;
      }

      const command = extractCommand(finalText);

      if (!command || commandRunningRef.current) {
        return;
      }

      commandRunningRef.current = true;

      setDetectedCommand(command);
      setTranscript("");
      setListening(false);

      stopRecognition(true);

      try {
        await onCommand(command);
      } catch (caughtError) {
        setError(
          caughtError?.message ||
            "The voice command could not be processed."
        );
      } finally {
        commandRunningRef.current = false;
      }
    };

    recognition.onerror = (event) => {
      if (
        event.error === "aborted" ||
        event.error === "no-speech"
      ) {
        return;
      }

      if (event.error === "not-allowed") {
        setError(
          "Microphone access was denied. Allow microphone access in the browser and try again."
        );

        enabledRef.current = false;
        setEnabled(false);
        return;
      }

      setError(
        `Voice recognition error: ${event.error}`
      );
    };

    recognition.onend = () => {
      if (!mountedRef.current) {
        return;
      }

      setListening(false);

      if (
        enabledRef.current &&
        !disabled &&
        !busy &&
        !speaking &&
        !commandRunningRef.current
      ) {
        window.setTimeout(
          startRecognition,
          500
        );
      }
    };

    recognitionRef.current = recognition;

    return () => {
      mountedRef.current = false;
      enabledRef.current = false;

      try {
        recognition.abort();
      } catch {
        // Ignore unmount cleanup errors.
      }
    };
  }, [
    onCommand,
    disabled,
    busy,
    speaking,
    startRecognition,
    stopRecognition,
  ]);


  useEffect(() => {
    if (!enabledRef.current) {
      return;
    }

    if (disabled || busy || speaking) {
      stopRecognition(true);
      setListening(false);
      return;
    }

    window.setTimeout(
      startRecognition,
      500
    );
  }, [
    disabled,
    busy,
    speaking,
    startRecognition,
    stopRecognition,
  ]);


  function getState() {
    if (speaking) {
      return {
        label: "Speaking",
        detail: "Playing the AI response",
        icon: Volume2,
        className: "speaking",
      };
    }

    if (busy) {
      return {
        label: "Thinking",
        detail: "Searching and preparing an answer",
        icon: LoaderCircle,
        className: "thinking",
      };
    }

    if (listening && enabled) {
      return {
        label: "Listening",
        detail: 'Say “Hey AI” followed by your question',
        icon: Mic,
        className: "listening",
      };
    }

    if (enabled) {
      return {
        label: "Waking up",
        detail: "Preparing microphone recognition",
        icon: LoaderCircle,
        className: "thinking",
      };
    }

    return {
      label: "Microphone off",
      detail: "Allow microphone once, then say “Hey AI…”",
      icon: MicOff,
      className: "off",
    };
  }


  if (!supported) {
    return (
      <div className="wake-control unavailable">
        <MicOff size={18} />

        <div>
          <strong>Voice unavailable</strong>
          <span>Use Chrome or Edge, or type below.</span>
        </div>
      </div>
    );
  }


  const state = getState();
  const StateIcon = state.icon;


  return (
    <aside
      className={`wake-control ${state.className}`}
      aria-live="polite"
    >
      <button
        type="button"
        className="wake-orb"
        aria-label={
          enabled
            ? "Pause hands-free voice mode"
            : "Turn on hands-free voice mode"
        }
        disabled={disabled && !enabled}
        onClick={
          enabled
            ? deactivateVoice
            : activateVoice
        }
      >
        <StateIcon
          size={23}
          className={
            state.className === "thinking"
              ? "spin"
              : ""
          }
        />
      </button>

      <div className="wake-status">
        <strong>{state.label}</strong>
        <span>{state.detail}</span>

        {transcript && listening && (
          <p className="wake-heard">
            {transcript}
          </p>
        )}

        {detectedCommand && (
          <p className="wake-command">
            Asked: “{detectedCommand}”
          </p>
        )}

        {error && (
          <p className="wake-error">
            {error}
          </p>
        )}
      </div>

      <button
        type="button"
        className="wake-toggle"
        onClick={
          enabled
            ? deactivateVoice
            : activateVoice
        }
      >
        {enabled ? "Pause" : "Allow microphone"}
      </button>
    </aside>
  );
}
