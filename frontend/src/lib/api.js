const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "";


export class ApiError extends Error {
  constructor(message, status, body = null) {
    super(message);

    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}


async function parseResponse(response) {
  const contentType =
    response.headers.get("content-type") || "";

  let body = null;

  if (contentType.includes("application/json")) {
    body = await response.json();
  } else {
    body = await response.text();
  }

  if (!response.ok) {
    const detail =
      typeof body === "object" && body?.detail
        ? body.detail
        : body;

    const message =
      typeof detail === "string"
        ? detail
        : detail
          ? JSON.stringify(detail)
          : `Request failed with HTTP ${response.status}`;

    throw new ApiError(
      message,
      response.status,
      body
    );
  }

  return body;
}


async function request(path, options = {}) {
  const response = await fetch(
    `${API_BASE_URL}${path}`,
    {
      ...options,

      headers: {
        ...(options.body instanceof FormData
          ? {}
          : {
              "Content-Type": "application/json",
            }),

        ...options.headers,
      },
    }
  );

  return parseResponse(response);
}


export function getHealth() {
  return request("/api/health");
}


export function listSessions() {
  return request("/api/sessions");
}


export function createSession({
  title,
  source,
  webexUrl = null,
}) {
  return request("/api/sessions", {
    method: "POST",

    body: JSON.stringify({
      title,
      source,
      webex_url: webexUrl,
      deidentified: true,
    }),
  });
}


export function createRecallWebexSession({
  meetingUrl,
  title,
}) {
  return request("/api/webex-realtime/start", {
    method: "POST",

    body: JSON.stringify({
      meeting_url: meetingUrl,
      title,
      deidentified: true,
    }),
  });
}


export function getRecallStatus(sessionId) {
  return request(
    `/api/recall/sessions/${sessionId}/status`
  );
}


export function getTranscript(
  sessionId,
  afterSequence = 0
) {
  const numericSequence =
    Number(afterSequence) || 0;

  const query =
    numericSequence > 0
      ? `?after_sequence=${encodeURIComponent(
          numericSequence
        )}`
      : "";

  return request(
    `/api/sessions/${sessionId}/transcript${query}`
  );
}


export function pasteTranscript({
  sessionId,
  transcript,
  defaultSpeaker = "Presenter",
}) {
  return request(
    `/api/sessions/${sessionId}/transcript/paste`,
    {
      method: "POST",

      body: JSON.stringify({
        transcript,
        default_speaker: defaultSpeaker,
      }),
    }
  );
}


export function uploadTranscript({
  sessionId,
  file,
}) {
  const formData = new FormData();

  formData.append("file", file);
  formData.append(
    "default_speaker",
    "Presenter"
  );

  return request(
    `/api/sessions/${sessionId}/transcript/upload`,
    {
      method: "POST",
      body: formData,
    }
  );
}


export function uploadMedia({
  sessionId,
  file,
}) {
  const formData = new FormData();

  formData.append("file", file);

  return request(
    `/api/sessions/${sessionId}/media/upload`,
    {
      method: "POST",
      body: formData,
    }
  );
}


export function askAssistant({
  sessionId,
  question,
  speak = true,
}) {
  return request(
    `/api/sessions/${sessionId}/ask`,
    {
      method: "POST",

      body: JSON.stringify({
        question,
        speak,
      }),
    }
  );
}


export function getResponses(sessionId) {
  return request(
    `/api/sessions/${sessionId}/responses`
  );
}


export function getAudioUrl(audioUrl) {
  if (!audioUrl) {
    return "";
  }

  return `${API_BASE_URL}${audioUrl}`;
}


export function createSpeech(text) {
  return request("/api/speech", {
    method: "POST",

    body: JSON.stringify({
      text,
    }),
  });
}


export function storeFoxResponse({
  sessionId,
  responseId,
  text,
}) {
  return request(
    `/api/sessions/${sessionId}/transcript/ai-response`,
    {
      method: "POST",
      body: JSON.stringify({
        response_id: responseId,
        text,
      }),
    }
  );
}
