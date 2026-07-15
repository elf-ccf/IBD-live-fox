const statusEl = document.getElementById("status");
const debugEl = document.getElementById("debug");
const dotEl = document.getElementById("dot");

const params = new URLSearchParams(window.location.search);
const relayUrl = params.get("wss");

let recorder = null;
let player = null;
let socket = null;
let disposed = false;

function setDot(state) {
  if (!dotEl) {
    return;
  }

  dotEl.className = `dot ${state}`;
}

function setStatus(state, message) {
  setDot(state);

  if (statusEl) {
    statusEl.textContent = message;
  }

  log("status", { state, message });
}

function log(message, payload = null) {
  const text = payload ? `${message}: ${JSON.stringify(payload).slice(0, 280)}` : message;

  if (debugEl) {
    debugEl.textContent = `${new Date().toISOString()} ${text}\n${debugEl.textContent}`.slice(0, 3500);
  }

  if (payload && payload.type === "input_audio_buffer.append") {
    return;
  }

  console.log(`[Webex Agent] ${text}`);
}

function float32ToInt16(input) {
  const output = new Int16Array(input.length);

  for (let index = 0; index < input.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, input[index]));
    output[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }

  return output;
}

function int16ToFloat32(input) {
  const output = new Float32Array(input.length);

  for (let index = 0; index < input.length; index += 1) {
    output[index] = input[index] / 0x8000;
  }

  return output;
}

function int16ToBase64(input) {
  const bytes = new Uint8Array(input.buffer, input.byteOffset, input.byteLength);

  let binary = "";
  const chunkSize = 0x8000;

  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    const chunk = bytes.subarray(offset, Math.min(offset + chunkSize, bytes.length));
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary);
}

function base64ToInt16(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
}

function resampleFloat32Linear(input, inputRate, outputRate) {
  if (inputRate === outputRate || input.length === 0) {
    return new Float32Array(input);
  }

  const ratio = outputRate / inputRate;
  const outputLength = Math.max(1, Math.floor(input.length * ratio));
  const output = new Float32Array(outputLength);

  for (let index = 0; index < outputLength; index += 1) {
    const sourcePosition = index / ratio;
    const leftIndex = Math.floor(sourcePosition);
    const rightIndex = Math.min(leftIndex + 1, input.length - 1);
    const fraction = sourcePosition - leftIndex;

    output[index] = input[leftIndex] + (input[rightIndex] - input[leftIndex]) * fraction;
  }

  return output;
}

class Pcm16Recorder {
  constructor(sampleRate) {
    this.targetSampleRate = sampleRate;
    this.audioContext = null;
    this.stream = null;
    this.sourceNode = null;
    this.processorNode = null;
    this.silentGainNode = null;
    this.callback = null;
  }

  async begin() {
    if (this.audioContext) {
      return;
    }

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });

    this.audioContext = new AudioContext();
    await this.audioContext.resume();

    this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);
    this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1);
    this.silentGainNode = this.audioContext.createGain();
    this.silentGainNode.gain.value = 0;

    this.processorNode.onaudioprocess = (event) => {
      if (!this.callback || !this.audioContext) {
        return;
      }

      const mono = event.inputBuffer.getChannelData(0);
      const resampled = resampleFloat32Linear(mono, this.audioContext.sampleRate, this.targetSampleRate);
      this.callback({ mono: resampled });
    };
  }

  async record(callback) {
    if (!this.audioContext || !this.sourceNode || !this.processorNode || !this.silentGainNode) {
      throw new Error("Recorder is not initialized.");
    }

    this.callback = callback;

    this.sourceNode.connect(this.processorNode);
    this.processorNode.connect(this.silentGainNode);
    this.silentGainNode.connect(this.audioContext.destination);

    await this.audioContext.resume();
  }

  async pause() {
    this.callback = null;

    try {
      this.sourceNode?.disconnect();
    } catch (_error) {
      // Ignore disconnect noise.
    }

    try {
      this.processorNode?.disconnect();
    } catch (_error) {
      // Ignore disconnect noise.
    }

    try {
      this.silentGainNode?.disconnect();
    } catch (_error) {
      // Ignore disconnect noise.
    }
  }

  async end() {
    await this.pause();

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
    }

    if (this.audioContext) {
      await this.audioContext.close();
    }

    this.stream = null;
    this.audioContext = null;
    this.sourceNode = null;
    this.processorNode = null;
    this.silentGainNode = null;
  }
}

class Pcm16StreamPlayer {
  constructor(sampleRate) {
    this.sampleRate = sampleRate;
    this.audioContext = null;
    this.nextPlaybackTime = 0;
  }

  async connect() {
    if (this.audioContext) {
      if (this.audioContext.state === "suspended") {
        await this.audioContext.resume();
      }
      return;
    }

    this.audioContext = new AudioContext({ latencyHint: "interactive" });
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }
    this.nextPlaybackTime = this.audioContext.currentTime;
  }

  async ensureRunning() {
    if (!this.audioContext) {
      return;
    }

    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }
  }

  async add16BitPCM(pcm, itemId = "response") {
    if (!this.audioContext) {
      throw new Error("Player is not connected.");
    }

    await this.ensureRunning();

    const floatData = int16ToFloat32(pcm);
    const buffer = this.audioContext.createBuffer(1, floatData.length, this.sampleRate);
    buffer.copyToChannel(floatData, 0);

    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(this.audioContext.destination);

    const now = this.audioContext.currentTime + 0.02;
    if (this.nextPlaybackTime < now) {
      this.nextPlaybackTime = now;
    }

    source.start(this.nextPlaybackTime);
    this.nextPlaybackTime += buffer.duration;

    log("audio.chunk.scheduled", {
      itemId,
      samples: pcm.length,
      nextPlaybackTime: Number(this.nextPlaybackTime.toFixed(3)),
    });
  }

  async interrupt() {
    if (!this.audioContext) {
      return;
    }

    await this.audioContext.close();
    this.audioContext = null;
    this.nextPlaybackTime = 0;
  }
}

function connectRelay() {
  if (!relayUrl) {
    setStatus("error", "Connection error: missing wss query parameter");
    log("wss.missing");
    return;
  }

  setStatus("connecting", "Connecting");
  recorder = new Pcm16Recorder(24000);
  player = new Pcm16StreamPlayer(24000);

  Promise.all([recorder.begin(), player.connect()])
    .then(() => {
      if (disposed) {
        return;
      }

      socket = new WebSocket(relayUrl, ["realtime"]);

      socket.onopen = async () => {
        log("ws.connected", { relayUrl });
        setStatus("connected", "Connected");

        await recorder.record((data) => {
          if (!socket || socket.readyState !== WebSocket.OPEN) {
            return;
          }

          const pcm16 = float32ToInt16(data.mono);

          socket.send(
            JSON.stringify({
              type: "input_audio_buffer.append",
              audio: int16ToBase64(pcm16),
            })
          );
        });

        setStatus("listening", "Listening for Hey Fox");
      };

      socket.onmessage = async (websocketEvent) => {
        let event = null;

        try {
          event = JSON.parse(websocketEvent.data);
        } catch (error) {
          log("ws.invalid.json", { message: error?.message || "unknown" });
          return;
        }

        const eventType = String(event?.type || "");

        if (eventType === "response.output_audio.delta" || eventType === "response.audio.delta") {
          if (!event.delta) {
            return;
          }

          const pcm = base64ToInt16(event.delta);

          log("audio.chunk.received", {
            type: eventType,
            samples: pcm.length,
          });

          try {
            await player.add16BitPCM(
              pcm,
              event.item_id || event.response_id || "fox-response"
            );
            setStatus("speaking", "Speaking");
          } catch (error) {
            console.error("[Webex Agent] playback failure", error);
            setStatus("error", "Playback failure");
            log("playback.failure", {
              message: error?.message || "unknown",
            });
          }

          return;
        }

        if (
          eventType === "response.output_audio.done" ||
          eventType === "response.audio.done" ||
          eventType === "response.done"
        ) {
          setStatus("listening", "Listening for Hey Fox");
          return;
        }

        if (
          eventType === "response.output_audio_transcript.done" ||
          eventType === "response.audio_transcript.done"
        ) {
          log("output.transcript", {
            transcript: String(event.transcript || "").slice(0, 220),
          });
          return;
        }

        if (eventType === "error") {
          const message = String(event?.error?.message || "Realtime error");
          console.error("[Webex Agent] server error", event);
          setStatus("error", "Connection error");
          log("server.error", { message: message.slice(0, 220) });
          return;
        }
      };

      socket.onerror = () => {
        setStatus("error", "Connection error");
        log("ws.error");
      };

      socket.onclose = () => {
        if (!disposed) {
          setStatus("error", "Connection error");
          log("ws.closed");
          window.setTimeout(connectRelay, 1800);
        }
      };
    })
    .catch((error) => {
      console.error("[Webex Agent] startup failed", error);
      setStatus("error", "Connection error");
      log("startup.failure", {
        message: error?.message || "unknown",
      });
    });
}

window.addEventListener("beforeunload", async () => {
  disposed = true;

  try {
    socket?.close();
  } catch (_error) {
    // Ignore cleanup errors.
  }

  try {
    await recorder?.end();
  } catch (_error) {
    // Ignore cleanup errors.
  }

  try {
    await player?.interrupt();
  } catch (_error) {
    // Ignore cleanup errors.
  }
});

connectRelay();
