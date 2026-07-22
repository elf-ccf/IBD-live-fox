import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  Bot,
  MessageSquareText,
  Radio,
} from "lucide-react";


export default function TranscriptPanel({
  transcript,
  loading,
  showWebexTabs = false,
}) {
  const segments =
    transcript?.segments || [];

  const participantSegments = segments.filter(
    (segment) => !segment.is_ai_speaker
  );

  const foxSegments = segments.filter(
    (segment) => segment.is_ai_speaker
  );

  const [activeTab, setActiveTab] =
    useState("transcript");

  const [unreadFoxCount, setUnreadFoxCount] =
    useState(0);

  const previousFoxCountRef = useRef(
    foxSegments.length
  );

  useEffect(() => {
    if (!showWebexTabs) {
      setActiveTab("transcript");
      setUnreadFoxCount(0);
      previousFoxCountRef.current =
        foxSegments.length;
      return;
    }

    const previousCount =
      previousFoxCountRef.current;

    const currentCount =
      foxSegments.length;

    if (currentCount < previousCount) {
      setUnreadFoxCount(0);
    } else if (
      currentCount > previousCount &&
      activeTab !== "fox"
    ) {
      setUnreadFoxCount(
        (currentValue) =>
          currentValue +
          (currentCount - previousCount)
      );
    }

    previousFoxCountRef.current =
      currentCount;
  }, [
    activeTab,
    foxSegments.length,
    showWebexTabs,
  ]);

  function selectTab(tabName) {
    setActiveTab(tabName);

    if (tabName === "fox") {
      setUnreadFoxCount(0);
    }
  }

  const visibleSegments =
    showWebexTabs && activeTab === "fox"
      ? foxSegments
      : showWebexTabs
        ? participantSegments
        : segments;

  const emptyTitle =
    showWebexTabs && activeTab === "fox"
      ? "No Fox responses yet"
      : "Waiting for content";

  const emptyMessage =
    showWebexTabs && activeTab === "fox"
      ? (
          "Completed IBD Live Fox responses " +
          "will appear here."
        )
      : showWebexTabs
        ? (
            "Waiting for meeting speech. " +
            "New participant transcript " +
            "segments will appear here."
          )
        : (
            "Upload a transcript or recording, " +
            "or begin speaking after the Recall.ai " +
            "bot joins Webex."
          );

  return (
    <section className="workspace-card transcript-card">
      <header className="card-header">
        <div>
          <div className="section-eyebrow">
            LIVE CONTEXT
          </div>

          <h2>
            {showWebexTabs &&
            activeTab === "fox" ? (
              <Bot size={21} />
            ) : (
              <MessageSquareText size={21} />
            )}

            {showWebexTabs
              ? activeTab === "fox"
                ? "Fox Responses"
                : "Live Transcript"
              : "Transcript"}
          </h2>
        </div>

        <div className="segment-count">
          {visibleSegments.length} segments
        </div>
      </header>

      {showWebexTabs && (
        <div
          className="transcript-tabs"
          role="tablist"
          aria-label="Webex transcript views"
        >
          <button
            type="button"
            role="tab"
            aria-selected={
              activeTab === "transcript"
            }
            className={
              activeTab === "transcript"
                ? "transcript-tab active"
                : "transcript-tab"
            }
            onClick={() =>
              selectTab("transcript")
            }
          >
            <MessageSquareText size={16} />
            Live Transcript
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={
              activeTab === "fox"
            }
            className={
              activeTab === "fox"
                ? "transcript-tab active"
                : "transcript-tab"
            }
            onClick={() =>
              selectTab("fox")
            }
          >
            <Bot size={16} />
            Fox Responses

            {unreadFoxCount > 0 && (
              <span
                className="fox-unread-badge"
                aria-label={
                  `${unreadFoxCount} unread Fox responses`
                }
              >
                {unreadFoxCount}
              </span>
            )}
          </button>
        </div>
      )}

      <div
        className="transcript-scroll"
        role="tabpanel"
      >
        {loading &&
          visibleSegments.length === 0 && (
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

        {visibleSegments.map((segment) => (
          <article
            className={[
              "transcript-segment",
              segment.contains_wake_phrase
                ? "wake-segment"
                : "",
              segment.is_ai_speaker
                ? "fox-response-segment"
                : "",
            ]
              .filter(Boolean)
              .join(" ")}
            key={
              segment.id ||
              `${segment.sequence_number}-${segment.created_at}`
            }
          >
            <div className="segment-heading">
              <strong>
                {segment.is_ai_speaker
                  ? "IBD Live Fox"
                  : segment.speaker_name ||
                    "Speaker"}
              </strong>

              <span>
                #{segment.sequence_number}
              </span>
            </div>

            <p>{segment.text}</p>

            {segment.contains_wake_phrase &&
              !segment.is_ai_speaker && (
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
