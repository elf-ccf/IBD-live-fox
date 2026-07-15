import {
  Activity,
  Bot,
  FileText,
  Film,
  FlaskConical,
  Mic,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Upload,
  Video,
  Wifi,
} from "lucide-react";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import "./App.css";
import "./modern.css";

import AnalysisPanel from "./components/AnalysisPanel";
import StatusBadge from "./components/StatusBadge";
import TranscriptPanel from "./components/TranscriptPanel";
import VoiceAssistant from "./components/VoiceAssistant";

import {
  ApiError,
  askAssistant,
  createRecallWebexSession,
  createSession,
  getAudioUrl,
  getHealth,
  getRecallStatus,
  getTranscript,
  pasteTranscript,
  uploadMedia,
  uploadTranscript,
} from "./lib/api";


import RealtimeFoxLauncher from "./components/RealtimeFoxLauncher";
const SAMPLE_TRANSCRIPT = `Dr. Patel: This is a simulated and fully de-identified educational case.

Dr. Patel: A patient with Crohn disease presents with worsening right lower-quadrant abdominal pain.

Dr. Morgan: The patient reports intermittent fever and reduced appetite. Inflammatory markers are elevated despite biologic therapy.

Dr. Patel: Cross-sectional imaging demonstrates terminal ileal thickening with an adjacent fluid collection.

Moderator: The patient is currently hemodynamically stable.`;


const INPUT_MODES = [
  {
    id: "webex",
    title: "Live Webex",
    description:
      "Send Recall.ai into a live Webex meeting.",
    icon: Video,
  },
  {
    id: "transcript",
    title: "Transcript",
    description:
      "Paste text or upload TXT, VTT, or SRT.",
    icon: FileText,
  },
  {
    id: "media",
    title: "Recording",
    description:
      "Upload meeting audio or video.",
    icon: Film,
  },
];


const QUICK_COMMANDS = [
  {
    label: "Ask about this case",
    prompt:
      "What are the most important insights from this presentation?",
  },
  {
    label: "Current evidence",
    prompt:
      "Search current reliable sources for information relevant to this presentation and explain the findings.",
  },
  {
    label: "Latest guidance",
    prompt:
      "What is the latest authoritative guidance relevant to the topic discussed in this presentation?",
  },
  {
    label: "Educational differential",
    prompt:
      "Provide an educational differential analysis grounded in the presentation and current reliable information.",
  },
  {
    label: "Missing information",
    prompt:
      "What important information is missing before this case can be interpreted more confidently?",
  },
];


const STAGE_LABELS = {
  idle: "Ready",
  creating_session: "Creating session",
  uploading: "Uploading",
  transcribing: "Transcribing",
  loading_transcript: "Loading transcript",
  ready: "Ready",
  analyzing: "Analyzing",
  generating_voice: "Generating voice",
  completed: "Completed",
  joining: "Joining Webex",
  listening: "Listening",
  failed: "Failed",
};


function mapRecallStatusToWebexStatus(data) {
  const status = String(data?.session_status || "").toLowerCase();
  const transcriptSegments = Number(data?.transcript_segment_count || 0);

  if (status === "speaking") {
    return "speaking";
  }

  if (status === "listening") {
    return "listening_for_hey_fox";
  }

  if (status === "joining") {
    return transcriptSegments > 0
      ? "joining_webex"
      : "waiting_for_admission";
  }

  if (status === "created") {
    return "waiting_for_admission";
  }

  if (status === "completed") {
    return "disconnected";
  }

  if (status === "failed") {
    return "error";
  }

  return "joining_webex";
}


function formatError(error) {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "An unexpected error occurred.";
}


function normalizeTranscript(data) {
  const segments = Array.isArray(data?.segments)
    ? data.segments
    : [];

  return {
    ...(data || {}),
    segments,
    segment_count:
      data?.segment_count ?? segments.length,
    transcript: data?.transcript || "",
  };
}


export default function App() {
  const [health, setHealth] = useState(null);
  const [mode, setMode] = useState("transcript");

  const [sessionId, setSessionId] =
    useState("");

  const [recallBotId, setRecallBotId] =
    useState("");

  const [workflowStage, setWorkflowStage] =
    useState("idle");

  const [webexStatus, setWebexStatus] =
    useState("ready");

  const [sessionTitle, setSessionTitle] =
    useState("IBD Educational Session");

  const [webexUrl, setWebexUrl] =
    useState("");

  const [pastedTranscript, setPastedTranscript] =
    useState(SAMPLE_TRANSCRIPT);

  const [selectedFile, setSelectedFile] =
    useState(null);

  const [transcript, setTranscript] =
    useState(normalizeTranscript(null));

  const [question, setQuestion] =
    useState("");

  const [analysisResult, setAnalysisResult] =
    useState(null);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [
    voicePlaying,
    setVoicePlaying,
  ] = useState(false);

  const audioRef = useRef(null);

  const playedAudioUrlRef = useRef("");


  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((caughtError) => {
        setError(
          `Backend unavailable: ${formatError(
            caughtError
          )}`
        );
      });
  }, []);

  const refreshTranscript = useCallback(
    async (targetSessionId = sessionId) => {
      if (!targetSessionId) {
        return null;
      }

      try {
        const data = await getTranscript(
          targetSessionId
        );

        const normalized =
          normalizeTranscript(data);

        setTranscript(normalized);

        return normalized;
      } catch (caughtError) {
        console.warn(
          "Transcript refresh failed:",
          caughtError
        );

        return null;
      }
    },
    [sessionId]
  );


  const refreshWebexStatus = useCallback(
    async () => {
      if (!sessionId || mode !== "webex") {
        return;
      }

      try {
        const data =
          await getRecallStatus(sessionId);

        if (data?.recall_bot_id && !recallBotId) {
          setRecallBotId(String(data.recall_bot_id));
        }

        setWebexStatus(mapRecallStatusToWebexStatus(data));
      } catch (caughtError) {
        console.warn(
          "Recall.ai status refresh failed:",
          caughtError
        );
      }
    },
    [mode, recallBotId, sessionId]
  );


  useEffect(() => {
    if (!sessionId || mode !== "webex") {
      return undefined;
    }

    refreshTranscript();
    refreshWebexStatus();

    const interval = window.setInterval(() => {
      refreshTranscript();
      refreshWebexStatus();
    }, 4000);

    return () => {
      window.clearInterval(interval);
    };
  }, [
    mode,
    sessionId,
    refreshTranscript,
    refreshWebexStatus,
  ]);
  useEffect(() => {
    const audioUrl = analysisResult?.fullAudioUrl;

    if (!audioUrl || !audioRef.current) {
      return undefined;
    }

    if (playedAudioUrlRef.current === audioUrl) {
      return undefined;
    }

    playedAudioUrlRef.current = audioUrl;

    const timer = window.setTimeout(async () => {
      try {
        audioRef.current.load();
        await audioRef.current.play();
      } catch {
        setMessage(
          "Answer ready. Browser blocked autoplay, so select Play response once."
        );
      }
    }, 500);

    return () => {
      window.clearTimeout(timer);
    };
  }, [analysisResult?.fullAudioUrl]);


  async function runAnalysis(
    targetSessionId,
    requestedQuestion,
    options = {}
  ) {
    const {
      autoPlay = true,
      showCompletionMessage = true,
    } = options;

    setWorkflowStage("analyzing");
    setError("");

    try {
      const result = await askAssistant({
        sessionId: targetSessionId,
        question: requestedQuestion,
        speak: true,
      });

      const completeResult = {
        ...result,
        fullAudioUrl: getAudioUrl(
          result.audio_url
        ),
      };

      setAnalysisResult(completeResult);
      setWorkflowStage("completed");

      if (showCompletionMessage) {
        setMessage(
          completeResult.fullAudioUrl
            ? "Answer ready. Speaking now."
            : "Answer ready."
        );
      }

      return completeResult;
    } catch (caughtError) {
      setWorkflowStage("failed");
      setError(formatError(caughtError));
      throw caughtError;
    }
  }


  async function createPastedSession() {
    if (!pastedTranscript.trim()) {
      setError(
        "Paste or enter a transcript first."
      );
      return;
    }

    setWorkflowStage("creating_session");
    setError("");
    setMessage("");
    setAnalysisResult(null);

    try {
      const session = await createSession({
        title:
          sessionTitle.trim() ||
          "Pasted transcript",
        source: "transcript_upload",
      });

      setWorkflowStage("uploading");

      await pasteTranscript({
        sessionId: session.id,
        transcript: pastedTranscript,
        defaultSpeaker: "Presenter",
      });

      setWorkflowStage("loading_transcript");

      const storedTranscript =
        normalizeTranscript(
          await getTranscript(session.id)
        );

      setSessionId(session.id);
      setTranscript(storedTranscript);
      setWorkflowStage("ready");

      setMessage(
        `${storedTranscript.segment_count} transcript segments stored. Preparing the initial summary…`
      );

      await runAnalysis(
        session.id,
        "Summarize the presentation for the panel. Clearly identify the key findings and important missing information.",
        {
          autoPlay: false,
          showCompletionMessage: true,
        }
      );
    } catch (caughtError) {
      if (workflowStage !== "failed") {
        setWorkflowStage("failed");
        setError(formatError(caughtError));
      }
    }
  }


  async function createTranscriptFileSession() {
    if (!selectedFile) {
      setError(
        "Choose a TXT, VTT, or SRT file."
      );
      return;
    }

    setWorkflowStage("creating_session");
    setError("");
    setMessage("");
    setAnalysisResult(null);

    try {
      const session = await createSession({
        title:
          sessionTitle.trim() ||
          selectedFile.name,
        source: "transcript_upload",
      });

      setWorkflowStage("uploading");

      await uploadTranscript({
        sessionId: session.id,
        file: selectedFile,
      });

      setWorkflowStage("loading_transcript");

      const storedTranscript =
        normalizeTranscript(
          await getTranscript(session.id)
        );

      setSessionId(session.id);
      setTranscript(storedTranscript);
      setWorkflowStage("ready");

      setMessage(
        `${storedTranscript.segment_count} transcript segments uploaded. Preparing the initial summary…`
      );

      await runAnalysis(
        session.id,
        "Summarize the presentation for the panel. Clearly identify the key findings and important missing information.",
        {
          autoPlay: false,
          showCompletionMessage: true,
        }
      );
    } catch (caughtError) {
      if (workflowStage !== "failed") {
        setWorkflowStage("failed");
        setError(formatError(caughtError));
      }
    }
  }


  async function createMediaFileSession() {
    if (!selectedFile) {
      setError(
        "Choose an audio or video recording."
      );
      return;
    }

    setWorkflowStage("creating_session");
    setError("");
    setMessage("");
    setAnalysisResult(null);

    try {
      const session = await createSession({
        title:
          sessionTitle.trim() ||
          selectedFile.name,
        source: "media_upload",
      });

      setSessionId(session.id);
      setWorkflowStage("uploading");
      setMessage("Uploading the recording…");

      setWorkflowStage("transcribing");
      setMessage(
        "Transcribing the recording with OpenAI…"
      );

      const uploadResult = await uploadMedia({
        sessionId: session.id,
        file: selectedFile,
      });

      setWorkflowStage("loading_transcript");

      const storedTranscript =
        uploadResult?.segments
          ? normalizeTranscript(uploadResult)
          : normalizeTranscript(
              await getTranscript(session.id)
            );

      setTranscript(storedTranscript);
      setWorkflowStage("ready");

      setMessage(
        `${storedTranscript.segment_count} transcript segments created. Preparing the initial summary…`
      );

      await runAnalysis(
        session.id,
        "Summarize the presentation for the panel. Clearly identify the key findings and important missing information.",
        {
          autoPlay: false,
          showCompletionMessage: true,
        }
      );
    } catch (caughtError) {
      setWorkflowStage("failed");
      setError(formatError(caughtError));
    }
  }


  async function startWebexSession() {
    if (!webexUrl.trim()) {
      setError(
        "Enter the complete Webex meeting URL."
      );
      return;
    }

    setWorkflowStage("joining");
    setWebexStatus("creating_bot");
    setError("");
    setMessage("");
    setAnalysisResult(null);
    setTranscript(normalizeTranscript(null));
    setRecallBotId("");

    try {
      const result =
        await createRecallWebexSession({
          meetingUrl: webexUrl.trim(),
          title:
            sessionTitle.trim() ||
            "Live Webex session",
        });

      setSessionId(result.session_id);
      setRecallBotId(result.recall_bot_id || "");
      setWebexStatus("waiting_for_admission");
      setWorkflowStage("ready");

      setMessage(
        `Recall.ai created Fox. Admit “${result.bot_name}” into Webex, then wait for Listening for Hey Fox.`
      );
    } catch (caughtError) {
      setWorkflowStage("failed");
      setWebexStatus("error");
      setError(formatError(caughtError));
    }
  }


  async function submitQuestion(
    requestedQuestion = question
  ) {
    const cleanedQuestion =
      requestedQuestion.trim();

    if (!sessionId) {
      setError(
        "Add a transcript, recording, or Webex meeting first."
      );
      return;
    }

    if (!cleanedQuestion) {
      setError("Enter a question for AI.");
      return;
    }

    setQuestion(cleanedQuestion);
    setMessage("");

    try {
      await runAnalysis(
        sessionId,
        cleanedQuestion,
        {
          autoPlay: true,
          showCompletionMessage: true,
        }
      );
    } catch {
      // runAnalysis handles the visible error.
    }
  }


  async function playAudio() {
    if (!audioRef.current) {
      setError(
        "No generated audio is available."
      );
      return;
    }

    try {
      audioRef.current.load();
      await audioRef.current.play();
    } catch (caughtError) {
      setError(
        `Audio playback failed: ${formatError(
          caughtError
        )}`
      );
    }
  }


  function changeMode(nextMode) {
    audioRef.current?.pause();

    setMode(nextMode);
    setSessionId("");
    setRecallBotId("");
    setWorkflowStage("idle");
    setWebexStatus(
      nextMode === "webex"
        ? "ready"
        : "offline"
    );
    setSelectedFile(null);
    setTranscript(normalizeTranscript(null));
    setAnalysisResult(null);
    setMessage("");
    setError("");
  }


  const busyStages = new Set([
    "creating_session",
    "uploading",
    "transcribing",
    "loading_transcript",
    "analyzing",
    "generating_voice",
    "joining",
  ]);

  const isBusy = busyStages.has(
    workflowStage
  );

  const visibleStatus =
    mode === "webex"
      ? webexStatus
      : workflowStage;

  const showAnalysisRealtimeFox =
    mode === "transcript" || mode === "media";

  const foxTranscriptionPending =
    mode === "media" &&
    new Set([
      "creating_session",
      "uploading",
      "transcribing",
      "loading_transcript",
    ]).has(workflowStage);


  return (
    <main className="application-shell">
      <header className="top-navigation">
        <div className="brand">
          <div className="brand-icon">
            <Sparkles size={22} />
          </div>

          <div>
            <strong>
              IBD Live Fox Discussant
            </strong>

            <span>
              Educational intelligence workspace
            </span>
          </div>
        </div>

        <div className="header-status">
          <div className="backend-indicator">
            <span
              className={
                health
                  ? "connection-dot connected"
                  : "connection-dot"
              }
            />

            {health
              ? "Backend connected"
              : "Connecting"}
          </div>

          <StatusBadge
            status={visibleStatus}
          />
        </div>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <div className="hero-kicker">
            <FlaskConical size={16} />
            AI-ASSISTED MEDICAL EDUCATION
          </div>

          <h1>
            One workspace for live and recorded
            case discussions.
          </h1>

          <p>
            Connect Webex, import a transcript, or
            upload a recording. The system builds
            presentation context, produces an
            educational analysis, and generates an
            audience-ready AI voice response.
          </p>
        </div>

        <div className="hero-safety">
          <ShieldCheck size={26} />

          <div>
            <strong>
              De-identified educational use only
            </strong>

            <span>
              AI output is not a final diagnosis and
              does not replace professional judgment.
            </span>
          </div>
        </div>
      </section>

      <section className="mode-selector">
        {INPUT_MODES.map((item) => {
          const Icon = item.icon;

          return (
            <button
              type="button"
              className={
                mode === item.id
                  ? "mode-button active"
                  : "mode-button"
              }
              key={item.id}
              onClick={() =>
                changeMode(item.id)
              }
            >
              <div className="mode-icon">
                <Icon size={21} />
              </div>

              <div>
                <strong>{item.title}</strong>
                <span>{item.description}</span>
              </div>
            </button>
          );
        })}
      </section>

      <section className="setup-card">
        <div className="setup-heading">
          <div>
            <div className="section-eyebrow">
              SESSION SETUP
            </div>

            <h2>
              {mode === "webex" &&
                "Connect a Webex meeting"}
              {mode === "transcript" &&
                "Add a presentation transcript"}

              {mode === "media" &&
                "Upload a meeting recording"}
            </h2>
          </div>

          {sessionId && (
            <span className="session-id">
              Session {sessionId.slice(0, 8)}…
            </span>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="session-title">
            Session title
          </label>

          <input
            id="session-title"
            value={sessionTitle}
            onChange={(event) =>
              setSessionTitle(
                event.target.value
              )
            }
          />
        </div>

        {mode === "webex" && (
          <div className="mode-form">
            <div className="form-field">
              <label htmlFor="webex-url">
                Webex meeting URL
              </label>

              <div className="input-with-icon">
                <Wifi size={18} />

                <input
                  id="webex-url"
                  value={webexUrl}
                  placeholder="https://your-site.webex.com/meet/..."
                  onChange={(event) =>
                    setWebexUrl(
                      event.target.value
                    )
                  }
                />
              </div>
            </div>

            <button
              type="button"
              className="primary-button"
              disabled={isBusy}
              onClick={startWebexSession}
            >
              <Bot size={18} />
              {workflowStage === "joining"
                ? "Creating bot…"
                : "Send Fox to Webex"}
            </button>
          </div>
        )}

        {mode === "transcript" && (
          <div className="transcript-input-layout">
            <div className="form-field">
              <label htmlFor="transcript-text">
                Paste transcript
              </label>

              <textarea
                id="transcript-text"
                rows={11}
                value={pastedTranscript}
                onChange={(event) =>
                  setPastedTranscript(
                    event.target.value
                  )
                }
              />

              <button
                type="button"
                className="primary-button"
                disabled={isBusy}
                onClick={createPastedSession}
              >
                <FileText size={18} />
                Process pasted transcript
              </button>
            </div>

            <div className="upload-divider">
              <span>OR</span>
            </div>

            <div className="upload-area">
              <Upload size={28} />

              <strong>
                Upload transcript file
              </strong>

              <span>TXT, SRT, or VTT</span>

              <input
                type="file"
                accept=".txt,.srt,.vtt"
                onChange={(event) =>
                  setSelectedFile(
                    event.target.files?.[0] ||
                    null
                  )
                }
              />

              {selectedFile && (
                <div className="selected-file">
                  {selectedFile.name}
                </div>
              )}

              <button
                type="button"
                className="secondary-button"
                disabled={
                  isBusy || !selectedFile
                }
                onClick={
                  createTranscriptFileSession
                }
              >
                Upload and analyze
              </button>
            </div>
          </div>
        )}

        {mode === "media" && (
          <div className="upload-area media-upload">
            <Film size={35} />

            <strong>
              Upload meeting recording
            </strong>

            <span>
              MP3, MP4, M4A, MPEG, WAV,
              or WebM
            </span>

            <input
              type="file"
              accept=".mp3,.mp4,.m4a,.mpeg,.mpga,.wav,.webm"
              onChange={(event) =>
                setSelectedFile(
                  event.target.files?.[0] ||
                  null
                )
              }
            />

            {selectedFile && (
              <div className="selected-file">
                <Film size={15} />
                {selectedFile.name}
              </div>
            )}

            <button
              type="button"
              className="primary-button"
              disabled={
                isBusy || !selectedFile
              }
              onClick={createMediaFileSession}
            >
              <Upload size={18} />
              Upload, transcribe, and analyze
            </button>
          </div>
        )}

        {isBusy && (
          <div className="workflow-progress">
            <div className="spinner" />

            <div>
              <strong>
                {STAGE_LABELS[workflowStage]}
              </strong>

              <span>
                Please keep this page open while
                processing completes.
              </span>
            </div>
          </div>
        )}

        {message && (
          <div className="success-message">
            <Activity size={17} />
            {message}
          </div>
        )}

        {error && (
          <div className="error-message">
            <strong>Unable to complete request</strong>
            <span>{error}</span>
          </div>
        )}
      </section>

      <section className="workspace-layout">
        <TranscriptPanel
          transcript={transcript}
          loading={
            workflowStage ===
              "loading_transcript" ||
            workflowStage ===
              "transcribing"
          }
        />
          <AnalysisPanel
          result={analysisResult}
          stage={workflowStage}
          audioRef={audioRef}
          onPlayAudio={playAudio}
          onAudioPlay={() =>
            setVoicePlaying(true)
          }
          onAudioEnded={() =>
            setVoicePlaying(false)
          }
        />
      </section>

      <VoiceAssistant
        onCommand={submitQuestion}
        disabled={
          !sessionId ||
          transcript.segment_count < 1
        }
        busy={isBusy}
        speaking={voicePlaying}
      />

      {showAnalysisRealtimeFox && (
        <RealtimeFoxLauncher
          activeSessionId={sessionId}
          mode={mode}
          transcriptionPending={foxTranscriptionPending}
        />
      )}

      <section className="assistant-console">
        <header>
          <div>
            <div className="section-eyebrow">
              ASK AI
            </div>

            <h2>
              <Mic size={21} />
              Continue the discussion
            </h2>
          </div>

          <button
            type="button"
            className="icon-button"
            title="Refresh transcript"
            disabled={!sessionId || isBusy}
            onClick={() =>
              refreshTranscript()
            }
          >
            <RefreshCw size={18} />
          </button>
        </header>

        <div className="quick-commands">
          {QUICK_COMMANDS.map((command) => (
            <button
              type="button"
              key={command.label}
              disabled={!sessionId || isBusy}
              onClick={() =>
                submitQuestion(command.prompt)
              }
            >
              {command.label}
            </button>
          ))}
        </div>

        <div className="question-row">
          <div className="question-input">
            <Sparkles size={19} />

            <textarea
              rows={2}
              value={question}
              placeholder="Ask anything using the meeting content and current web information…"
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey
                ) {
                  event.preventDefault();
                  submitQuestion();
                }
              }}
            />
          </div>

          <button
            type="button"
            className="send-button"
            disabled={
              !sessionId ||
              isBusy ||
              !question.trim()
            }
            onClick={() => submitQuestion()}
          >
            <Send size={19} />
            Ask AI
          </button>
        </div>

        <div className="console-footer">
          <span>
            <ShieldCheck size={15} />
            Simulated or fully de-identified content only
          </span>

          <span>
            Current stage:{" "}
            {STAGE_LABELS[workflowStage] ||
              workflowStage}
          </span>
        </div>
      </section>
    </main>
  );
}
