import React from "react";
import {
  BookOpen,
  BrainCircuit,
  ExternalLink,
  FileWarning,
  Play,
  Sparkles,
  Volume2,
} from "lucide-react";


export default function AnalysisPanel({
  result,
  stage,
  audioRef,
  onPlayAudio,
  onAudioPlay,
  onAudioEnded,
}) {
  const answer = result?.answer;

  const processingStages = new Set([
    "analyzing",
    "generating_voice",
  ]);

  if (processingStages.has(stage)) {
    return (
      <section className="workspace-card analysis-card">
        <header className="card-header">
          <div>
            <div className="section-eyebrow">
              AI OUTPUT
            </div>

            <h2>
              <BrainCircuit size={21} />
              Educational analysis
            </h2>
          </div>
        </header>

        <div className="thinking-state">
          <div className="ai-orb">
            <Sparkles size={28} />
          </div>

          <h3>
            {stage === "generating_voice"
              ? "Preparing the spoken response"
              : "Understanding the presentation"}
          </h3>

          <p>
            {stage === "generating_voice"
              ? "OpenAI Voice is creating an audience-ready audio response."
              : "Reviewing presentation facts, external context, uncertainty, and educational differential possibilities."}
          </p>

          <div className="thinking-steps">
            <span>Case context</span>
            <span>Current evidence</span>
            <span>Reasoning</span>
            <span>Audience response</span>
          </div>
        </div>
      </section>
    );
  }

  if (!answer) {
    return (
      <section className="workspace-card analysis-card">
        <header className="card-header">
          <div>
            <div className="section-eyebrow">
              AI OUTPUT
            </div>

            <h2>
              <BrainCircuit size={21} />
              Educational analysis
            </h2>
          </div>
        </header>

        <div className="empty-area analysis-empty">
          <BrainCircuit size={38} />

          <h3>Analysis will appear here</h3>

          <p>
            Add a transcript or recording. The application
            will automatically prepare an initial summary,
            then you can continue asking questions.
          </p>
        </div>
      </section>
    );
  }

  const sources = Array.isArray(answer.sources)
    ? answer.sources
    : [];

  const differential = Array.isArray(
    answer.differential
  )
    ? answer.differential
    : [];

  return (
    <section className="workspace-card analysis-card">
      <header className="card-header">
        <div>
          <div className="section-eyebrow">
            AI OUTPUT
          </div>

          <h2>
            <BrainCircuit size={21} />
            Educational analysis
          </h2>
        </div>

        {result.web_search_used && (
          <div className="web-grounded-badge">
            Web grounded
          </div>
        )}
      </header>

      <div className="analysis-scroll">
        <article className="summary-panel">
          <h3>Presentation context</h3>
          <p>{answer.case_summary}</p>
        </article>

        {answer.key_findings?.length > 0 && (
          <div className="analysis-section">
            <h3>Key findings</h3>

            <ul>
              {answer.key_findings.map(
                (finding, index) => (
                  <li key={`${index}-${finding}`}>
                    {finding}
                  </li>
                )
              )}
            </ul>
          </div>
        )}

        {differential.length > 0 && (
          <div className="analysis-section">
            <h3>Educational differential</h3>

            <div className="differential-grid">
              {differential.map((item) => (
                <article
                  className="differential-item"
                  key={`${item.rank}-${item.condition}`}
                >
                  <div className="rank-circle">
                    {item.rank}
                  </div>

                  <div className="differential-body">
                    <div className="condition-row">
                      <h4>{item.condition}</h4>

                      <span className="likelihood">
                        {item.likelihood}
                      </span>
                    </div>

                    <p>{item.rationale}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        )}

        {answer.missing_information?.length > 0 && (
          <article className="missing-panel">
            <h3>
              <FileWarning size={18} />
              Missing information
            </h3>

            <ul>
              {answer.missing_information.map(
                (item, index) => (
                  <li key={`${index}-${item}`}>
                    {item}
                  </li>
                )
              )}
            </ul>
          </article>
        )}

        <article className="answer-panel">
          <h3>AI answer</h3>
          <p>{answer.answer}</p>
        </article>

        {sources.length > 0 && (
          <div className="analysis-section">
            <h3>
              <BookOpen size={18} />
              External sources
            </h3>

            <div className="source-list">
              {sources.map((source, index) => (
                <button
                  type="button"
                  className="source-item"
                  key={`${index}-${source.url}`}
                  onClick={() => {
                    if (source.url) {
                      window.open(
                        source.url,
                        "_blank",
                        "noopener,noreferrer"
                      );
                    }
                  }}
                >
                  <div>
                    <strong>
                      {source.title}
                    </strong>

                    {source.organization && (
                      <span>
                        {source.organization}
                      </span>
                    )}

                    {source.published_date && (
                      <span>
                        {source.published_date}
                      </span>
                    )}
                  </div>

                  <ExternalLink size={16} />
                </button>
              ))}
            </div>
          </div>
        )}

        <article className="audience-panel">
          <h3>
            <Volume2 size={18} />
            Audience response
          </h3>

          <p>{answer.audience_script}</p>

          {result.fullAudioUrl && (
            <div className="audio-controls">
              {React.createElement(
                "audio",
                {
                  ref: audioRef,
                  controls: true,
                  preload: "metadata",
                  src: result.fullAudioUrl,
                  onPlay: onAudioPlay,
                  onEnded: onAudioEnded,
                  onPause: onAudioEnded,
                },
                "Your browser does not support audio playback."
              )}

              <button
                type="button"
                className="secondary-button compact-button"
                onClick={onPlayAudio}
              >
                <Play size={17} />
                Play response
              </button>

              <span className="ai-voice-label">
                AI-generated voice
              </span>
            </div>
          )}

          {result.voice_error && (
            <div className="inline-error">
              Voice generation failed:{" "}
              {result.voice_error}
            </div>
          )}
        </article>

        <article className="limitations-panel">
          <strong>Limitations</strong>
          <p>{answer.limitations}</p>
        </article>
      </div>
    </section>
  );
}
