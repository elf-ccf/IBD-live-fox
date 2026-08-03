import React from "react";

import {
  BookOpen,
  BrainCircuit,
  ExternalLink,
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

  const isThinking = [
    "analyzing",
    "generating_voice",
  ].includes(stage);

  if (isThinking) {
    return (
      <section className="workspace-card analysis-card">
        <header className="card-header">
          <div>
            <div className="section-eyebrow">
              AI OUTPUT
            </div>

            <h2>
              <BrainCircuit size={21} />
              AI Answer
            </h2>
          </div>
        </header>

        <div className="thinking-state">
          <div className="ai-orb">
            <Sparkles size={28} />
          </div>

          <h3>Thinking</h3>

          <p>
            Searching the web and preparing a direct answer.
          </p>
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
              AI Answer
            </h2>
          </div>
        </header>

        <div className="empty-area analysis-empty">
          <BrainCircuit size={38} />

          <h3>Ask AI anything</h3>

          <p>
            Type a question to analyze the meeting content.
          </p>
        </div>
      </section>
    );
  }

  const sources = Array.isArray(answer.sources)
    ? answer.sources.slice(0, 3)
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
            AI Answer
          </h2>
        </div>

        {result.web_search_used && (
          <div className="web-grounded-badge">
            Web searched
          </div>
        )}
      </header>

      <div className="analysis-scroll">
        <article className="answer-panel primary-answer">
          <h3>Answer</h3>
          <p>{answer.answer}</p>
        </article>

        {result.fullAudioUrl && (
          <article className="audience-panel compact-audio-panel">
            <h3>
              <Volume2 size={18} />
              Spoken response
            </h3>

            {React.createElement(
              "audio",
              {
                ref: audioRef,
                controls: true,
                preload: "auto",
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

          </article>
        )}

        {result.voice_error && (
          <div className="inline-error">
            Voice generation failed: {result.voice_error}
          </div>
        )}

        {sources.length > 0 && (
          <details className="answer-details">
            <summary>
              Sources
            </summary>

            <div className="source-list">
              {sources.map((source, index) => (
                <button
                  type="button"
                  className="source-item"
                  key={`${index}-${source.url || source.title}`}
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
          </details>
        )}
      </div>
    </section>
  );
}
