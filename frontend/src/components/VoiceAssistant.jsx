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


const WAKE_PHRASES = [
  "hey fox",
  "hi fox",
  "okay fox",
  "ok fox",
  "hey box",
  "hey folks",
  "hey fax",
  "a fox",
  "fox",
];


function cleanText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}


function extractCommand(text) {
  const original = String(text || "").trim();

  if (!original) {
    return null;
  }

  const cleaned = cleanText(original);

  for (const wakePhrase of WAKE_PHRASES) {
    const cleanedWake = cleanText(wakePhrase);
    const index = cleaned.indexOf(cleanedWake);

    if (index >= 0) {
      const beforeWake = cleaned.slice(0, index);
      const afterWakeIndex =
        beforeWake.length + cleanedWake.length;

      const originalWords = original.split(/\s+/);
      const cleanedWords = cleaned.split(/\s+/);
      const wakeWords = cleanedWake.split(/\s+/);

      let startWordIndex = -1;

      for (
        let i = 0;
        i <= cleanedWords.length - wakeWords.length;
        i += 1
      ) {
        const chunk = cleanedWords
          .slice(i, i + wakeWords.length)
          .join(" ");

        if (chunk === cleanedWake) {
          startWordIndex = i + wakeWords.length;
          break;
        }
      }

      if (startWordIndex >= 0) {
        const command = originalWords
          .slice(startWordIndex)
          .join(" ")
          .replace(/^[\s,.:;!?—-]+/, "")
          .trim();

        return command || null;
      }

      const fallbackCommand = original
        .slice(afterWakeIndex)
        .replace(/^[\s,.:;!?—-]+/, "")
        .trim();

      return fallbackCommand || null;
    }
  }

  /*
    If voice mode is already enabled and the browser dropped
    the wake phrase, use the final recognized sentence as the
    command. This makes the experience feel Siri-like after
    the user has explicitly enabled the microphone.
  */
  const looksLikeQuestion =
    /\b(what|why|how|when|where|who|can|could|tell|explain|summarize|search|compare|give|show)\b/i
      .test(original);

  if (looksLikeQuestion) {
    return original;
  }

  return null;
}


export default function VoiceAssistant({
  onCommand,
  disabled = false,
  busy = false,
  speaking = false,
}) {
  const recognitionRef = useRef(null);
  const enabledRef = useRef(false);
  const commandRunningRef = useRef(false);

  const [supported, setSupported] =
    useState(true);

  const [enabled, setEnabled] =
    useState(false);

  const [listening, setListening] =
    useState(false);

  const [liveWords, setLiveWords] =
    useState("");

  const [lastHeard, setLastHeard] =
    useState("");

  const [lastCommand, setLastCommand] =
    useState("");

  const [error, setError] =
    useState("");


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
      // Already active.
    }
  }, [disabled, busy, speaking]);


  const stopRecognition = useCallback(() => {
    try {
      recognitionRef.current?.stop();
    } catch {
      // Already stopped.
    }
  }, []);


  function enableVoice() {
    setError("");
    setEnabled(true);
    enabledRef.current = true;

    window.setTimeout(
      startRecognition,
      180
    );
  }


  function pauseVoice() {
    enabledRef.current = false;
    setEnabled(false);
    setListening(false);
    stopRecognition();
  }


  useEffect(() => {
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
      setListening(true);
      setError("");
    };

    recognition.onresult = async (event) => {
      let interimText = "";
      let finalText = "";

      for (
        let index = event.resultIndex;
        index < event.results.length;
        index += 1
      ) {
        const result = event.results[index];
        const text =
          result[0]?.transcript || "";

        if (result.isFinal) {
          finalText += `${text} `;
        } else {
          interimText += `${text} `;
        }
      }

      const visible =
        (finalText || interimText).trim();

      if (visible) {
        setLiveWords(visible);
        setLastHeard(visible);
      }

      if (!finalText.trim()) {
        return;
      }

      const command =
        extractCommand(finalText);

      if (
        !command ||
        commandRunningRef.current
      ) {
        return;
      }

      commandRunningRef.current = true;

      setLastCommand(command);
      setLiveWords("");
      setListening(false);

      stopRecognition();

      try {
        await onCommand(command);
      } catch (caughtError) {
        setError(
          caughtError?.message ||
            "Unable to process voice command."
        );
      } finally {
        commandRunningRef.current = false;

        if (
          enabledRef.current &&
          !disabled &&
          !busy &&
          !speaking
        ) {
          window.setTimeout(
            startRecognition,
            900
          );
        }
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
          "Microphone permission denied."
        );

        setEnabled(false);
        enabledRef.current = false;
        return;
      }

      setError(
        `Microphone error: ${event.error}`
      );
    };

    recognition.onend = () => {
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
          800
        );
      }
    };

    recognitionRef.current = recognition;

    return () => {
      enabledRef.current = false;

      try {
        recognition.abort();
      } catch {
        // Ignore cleanup errors.
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

    if (busy || speaking || disabled) {
      stopRecognition();
      return;
    }

    window.setTimeout(
      startRecognition,
      800
    );
  }, [
    busy,
    speaking,
    disabled,
    startRecognition,
    stopRecognition,
  ]);


  if (!supported) {
    return (
      <section className="wake-control unavailable">
        <MicOff size={20} />

        <div className="wake-status">
          <strong>Voice unavailable</strong>
          <span>
            Use Chrome or Edge, or type your question.
          </span>
        </div>
      </section>
    );
  }


  let label = "Microphone off";
  let detail =
    "Allow microphone once, then say “Hey Fox…”";
  let Icon = MicOff;
  let stateClass = "off";

  if (speaking) {
    label = "Speaking";
    detail = "Playing the AI response";
    Icon = Volume2;
    stateClass = "speaking";
  } else if (busy) {
    label = "Thinking";
    detail = "Searching and preparing an answer";
    Icon = LoaderCircle;
    stateClass = "thinking";
  } else if (listening) {
    label = "Listening";
    detail =
      "Say “Hey Fox” followed by your question";
    Icon = Mic;
    stateClass = "listening";
  } else if (enabled) {
    label = "Ready";
    detail =
      "Waiting for the microphone to restart";
    Icon = LoaderCircle;
    stateClass = "thinking";
  }


  return (
    <section
      className={`wake-control ${stateClass}`}
      aria-live="polite"
    >
      <button
        type="button"
        className="wake-orb"
        onClick={
          enabled
            ? pauseVoice
            : enableVoice
        }
        disabled={disabled && !enabled}
        aria-label={
          enabled
            ? "Pause hands-free voice mode"
            : "Allow microphone for hands-free mode"
        }
      >
        <Icon
          size={22}
          className={
            stateClass === "thinking"
              ? "spin"
              : ""
          }
        />
      </button>

      <div className="wake-status">
        <strong>{label}</strong>
        <span>{detail}</span>

        {liveWords && (
          <p className="wake-heard">
            Heard: “{liveWords}”
          </p>
        )}

        {!liveWords && lastHeard && (
          <p className="wake-heard muted">
            Last heard: “{lastHeard}”
          </p>
        )}

        {lastCommand && (
          <p className="wake-command">
            Command: “{lastCommand}”
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
            ? pauseVoice
            : enableVoice
        }
        disabled={disabled && !enabled}
      >
        {enabled ? "Pause" : "Allow mic"}
      </button>
    </section>
  );
}
