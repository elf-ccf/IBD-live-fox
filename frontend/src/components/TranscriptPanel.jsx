import {
  MessageSquareText,
  Radio,
} from "lucide-react";


export default function TranscriptPanel({
  transcript,
  loading,
}) {
  const segments =
    transcript?.segments || [];

  return (
    <section className="workspace-card transcript-card">
      <header className="card-header">
        <div>
          <div className="section-eyebrow">
            LIVE CONTEXT
          </div>

          <h2>
            <MessageSquareText size={21} />
            Transcript
          </h2>
        </div>

        <div className="segment-count">
          {segments.length} segments
        </div>
      </header>

      <div className="transcript-scroll">
        {loading && segments.length === 0 && (
          <div className="empty-area">
            <div className="spinner" />

            <p>Loading transcript…</p>
          </div>
        )}

        {!loading && segments.length === 0 && (
          <div className="empty-area">
            <Radio size={34} />

            <h3>Waiting for content</h3>

            <p>
              Upload a transcript or recording,
              or begin speaking after the Recall.ai
              bot joins Webex.
            </p>
          </div>
        )}

        {segments.map((segment) => (
          <article
            className={
              segment.contains_wake_phrase
                ? "transcript-segment wake-segment"
                : "transcript-segment"
            }
            key={segment.id}
          >
            <div className="segment-heading">
              <strong>
                {segment.speaker_name}
              </strong>

              <span>
                #{segment.sequence_number}
              </span>
            </div>

            <p>{segment.text}</p>

            {segment.contains_wake_phrase && (
              <div className="wake-indicator">
                Wake command detected
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
