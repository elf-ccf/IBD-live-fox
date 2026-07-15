import {
  AlertCircle,
  CheckCircle2,
  LoaderCircle,
  Mic,
  Radio,
  Volume2,
} from "lucide-react";


const STATUS_CONFIGURATION = {
  created: {
    label: "Created",
    icon: CheckCircle2,
    tone: "neutral",
  },

  joining: {
    label: "Joining meeting",
    icon: LoaderCircle,
    tone: "processing",
  },

  listening: {
    label: "Listening",
    icon: Mic,
    tone: "success",
  },

  processing: {
    label: "Thinking",
    icon: LoaderCircle,
    tone: "processing",
  },

  speaking: {
    label: "Speaking",
    icon: Volume2,
    tone: "speaking",
  },

  completed: {
    label: "Completed",
    icon: CheckCircle2,
    tone: "success",
  },

  failed: {
    label: "Failed",
    icon: AlertCircle,
    tone: "danger",
  },

  offline: {
    label: "Offline",
    icon: Radio,
    tone: "neutral",
  },

  ready: {
    label: "Ready",
    icon: CheckCircle2,
    tone: "neutral",
  },

  creating_bot: {
    label: "Creating bot",
    icon: LoaderCircle,
    tone: "processing",
  },

  waiting_for_admission: {
    label: "Waiting for admission",
    icon: LoaderCircle,
    tone: "processing",
  },

  joining_webex: {
    label: "Joining Webex",
    icon: LoaderCircle,
    tone: "processing",
  },

  listening_for_hey_fox: {
    label: "Listening for Hey Fox",
    icon: Mic,
    tone: "success",
  },

  disconnected: {
    label: "Disconnected",
    icon: Radio,
    tone: "neutral",
  },

  error: {
    label: "Error",
    icon: AlertCircle,
    tone: "danger",
  },
};


export default function StatusBadge({
  status = "offline",
}) {
  const normalizedStatus =
    String(status).toLowerCase();

  const configuration =
    STATUS_CONFIGURATION[normalizedStatus] ||
    {
      label: status || "Unknown",
      icon: Radio,
      tone: "neutral",
    };

  const Icon = configuration.icon;

  return (
    <span
      className={
        `status-badge status-${configuration.tone}`
      }
    >
      <Icon
        size={15}
        className={
          configuration.tone === "processing"
            ? "spin"
            : ""
        }
      />

      {configuration.label}
    </span>
  );
}
