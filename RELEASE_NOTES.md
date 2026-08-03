# Release Notes — Clinical IQ v1.0 (FEK)

**Branch:** FEK  
**Date:** 2026-08-03  
**Base:** main (commit 271b1f2)

---

## Summary

This release rebrands the application from **IBD Live Fox** to **Clinical IQ**, significantly improves ease of setup, and refines the UI for clinical educational use. The bot now works with any supported online meeting platform (not just Webex) and the AI interaction model has been simplified and focused around three clinical presets.

---

## Changes

### Branding
- Renamed application from **IBD Live Fox** to **Clinical IQ** throughout: page title, header, backend config, transcript speaker labels, and bot display name.
- Updated hero copy to reflect multi-platform meeting support.

### Setup & Developer Experience
- Added `setup.sh` — a one-shot bash script that checks for Python 3.11+, creates a `backend/.venv` virtual environment, installs Python and npm dependencies, and scaffolds `backend/.env`. Replaces the lengthy manual steps previously required.
- Rewrote `README.md` with clear architecture diagrams, quick-setup instructions, and corrected environment variable documentation.

### Live Meeting
- Fixed Recall.ai region default: documentation and `.env.example` now reference `us-east-1` as the example region. Users must set `RECALL_REGION_BASE_URL` to match their account region.
- Changed UI label from "Connect a Webex meeting" to "Connect an online meeting".
- Removed Webex-specific messaging from status and error strings.

### Transcript
- **Fixed:** Switching between input mode tabs (Live Meeting / Transcript / Recording / Presentation) no longer wipes the loaded transcript. Content is preserved until a new session is explicitly started.

### Presentation Upload
- Raised the PPTX upload limit from **25 MB** to **200 MB** in both the backend validation and the frontend UI label.

### AI Interaction
- **Removed** the microphone / wake-phrase UI (`VoiceAssistant` component, "Hey Fox", "Allow mic" button, mic on/off toggle). Audio input from the meeting bot is unaffected.
- **New layout:** "Ask a question" section now appears directly below the transcript, followed by the AI answer output at the bottom.
- **Replaced** quick-command presets with three focused clinical presets:
  - **Summarize the case** — generates a clinical vignette, differential diagnosis, and next steps in management.
  - **Missing information** — identifies what information is missing before the case can be interpreted confidently.
  - **Latest guidance** — searches online for authoritative guidance relevant to the case.
- All three presets include a guard: if the content is not a clinical case, the AI replies accordingly.
- Updated empty-state text in the AI output panel to remove the microphone reference.

### Internal / Backend
- `app_name` config default updated to `"Clinical IQ"`.
- No database schema changes; existing SQLite databases are compatible.

---

## Known Limitations
- The ngrok free tunnel URL changes on every restart; `PUBLIC_BASE_URL` in `backend/.env` must be updated accordingly.
- The `VoiceAssistant` component file (`frontend/src/components/VoiceAssistant.jsx`) remains in the codebase but is no longer mounted. It can be removed in a future cleanup.
