# MailMind – AI Voice Email Assistant

MailMind is a local, single-user Streamlit application that combines voice input, AI writing assistance, Gmail, and Google Calendar in one email workspace. It turns spoken or typed instructions into editable drafts, helps users understand their inbox, and connects email actions to reminders and calendar events.

Speech recognition runs locally with Faster-Whisper. Text generation and email analysis use NVIDIA NIM through an OpenAI-compatible client. Users review messages and events before confirming external actions.

## Problem statement

Managing email involves more than reading and sending messages: users must write clear responses, identify urgent requests, track deadlines, and remember unanswered conversations. Switching between an inbox, notes, and a calendar makes these tasks easy to lose track of.

MailMind brings these workflows together with voice-assisted composition, on-demand email analysis, and reviewed next steps.

## Key features

| Feature | Implemented behavior |
| --- | --- |
| Voice-based email interaction | Record instructions for composition or search, transcribe locally, and edit the text before using it. |
| AI email drafting | Generate editable subjects and bodies with Professional, Friendly, Formal, or Concise tone. |
| Gmail sending | Validate a single recipient and message fields, preview the exact message, and confirm delivery. |
| Inbox access | Read the latest 10 inbox messages with sender, subject, received time, preview, and readable body. |
| Email summarization | Request a concise summary of an individual email from the Inbox. |
| Contextual replies | Generate, edit, regenerate, and explicitly confirm replies using the source email as context. |
| Scheduled emails | Store future messages in SQLite, send through a background worker, and manage pending messages and delivery history. |
| Smart reminders | Create persistent reminders, view upcoming/overdue/completed items, and receive dismissible Dashboard alerts. |
| Voice email search | Search by typed or transcribed queries, including supported spoken patterns and Gmail search syntax; return up to 20 inbox matches. |
| Priority classification | Classify individual messages as High, Medium, or Low priority with a short reason. |
| Action and deadline extraction | Extract meetings, interviews, appointments, tasks, submissions, and deadlines with available dates, times, and source context. |
| Action-to-reminder integration | Open an editable reminder from an extracted action and save it after confirmation. |
| Google Calendar events | Review extracted actions, supply event start/end details, and confirm creation in the primary calendar. |
| Follow-ups | Identify response-requesting sent conversations, show Waiting/Replied/Follow-up Needed status, and generate editable, confirmed follow-up messages. |

## Tech stack

| Layer | Technology and role |
| --- | --- |
| Language | Python |
| Interface | Streamlit, custom CSS, session state, and timed fragments |
| Speech recognition | Faster-Whisper, English `base.en`, CPU execution, `int8` computation |
| AI | NVIDIA NIM via the OpenAI Python SDK |
| Email | Gmail API, Python email/MIME utilities, `email-validator` |
| Calendar | Google Calendar API |
| Authentication | Google OAuth Desktop app flow and Google authentication libraries |
| Persistence | SQLite through Python's `sqlite3` module |
| Configuration | Environment variables and `python-dotenv` |
| Testing | pytest, mocks, temporary SQLite databases, and Streamlit AppTest |

## How the system works

1. **Capture:** Type an instruction or record audio in Compose Email or Voice Email Search.
2. **Transcribe:** Faster-Whisper converts recorded English speech into editable text locally.
3. **Draft or retrieve:** Generate a draft through NVIDIA NIM, or retrieve messages through Gmail.
4. **Understand:** Request summaries, contextual replies, priority labels, or action extraction for individual inbox messages.
5. **Review:** Check generated content, recipients, extracted dates, and local-time interpretations.
6. **Act:** Confirm an immediate send, authorize a scheduled message, save a reminder, or confirm a Calendar event.
7. **Track:** Review scheduled delivery history, Dashboard reminder alerts, and sent-conversation follow-ups.

```text
Microphone / typed input
          |
          v
Streamlit UI <---- Local Faster-Whisper transcription
    |
    +---- AI services -------------------- NVIDIA NIM
    +---- Email services ---------------- Gmail API
    +---- Reviewed extracted actions ----- Google Calendar API
    +---- Scheduling / reminders --------- SQLite
               |
               +---- Background email delivery / Dashboard alerts
```

## Project architecture

```text
.
├── app.py                         # Streamlit entry point
├── requirements.txt               # Runtime dependencies
├── requirements-dev.txt           # Runtime dependencies plus pytest
├── pytest.ini                     # Test import-path configuration
├── .env.example                   # Configuration template
├── .streamlit/config.toml         # Streamlit configuration
├── src/email_assistant/
│   ├── ai/                        # Drafts, summaries, replies, priority, actions, follow-ups
│   ├── calendar/                  # Event validation and confirmed creation
│   ├── email/                     # Gmail OAuth, sending, inbox, search, follow-up detection
│   ├── reminders/                 # Reminder validation and time handling
│   ├── scheduling/                # Scheduled delivery service and background worker
│   ├── storage/                   # SQLite repositories for messages and reminders
│   ├── ui/                        # Pages, forms, confirmation flows, and styling
│   ├── voice/                     # Local audio validation and transcription
│   ├── core/                      # Package scaffold
│   └── models/                    # Package scaffold
├── tests/                         # Service and UI tests
└── data/mailmind.db                # Created at runtime; ignored by Git
```

The UI coordinates review and confirmation, service modules handle provider calls and workflow rules, and storage modules manage persistence. Drafts and inbox analysis primarily use Streamlit session state; scheduled messages and reminders persist across restarts.

## Installation and setup

### Prerequisites

- Python 3.11 or newer is recommended; the test suite uses the standard-library `tomllib` module.
- A local browser and microphone permission for recording.
- Internet access for dependency installation, the first speech-model download, NVIDIA NIM, and Google APIs.
- NVIDIA API access for AI features and a Google account with a configured Desktop OAuth client for Gmail/Calendar features.

Download or clone this repository, then open a terminal in its root directory.

### Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Copy the template only when creating a new local configuration; retain an existing `.env` if already configured.

## Environment and configuration

Edit your local `.env` privately. Never paste real configuration values into documentation, issues, screenshots, or commits.

| Setting or file | Purpose |
| --- | --- |
| `NVIDIA_API_KEY` | Required for AI features; set your own value locally. |
| `NVIDIA_MODEL` | Optional model override. The code defaults to `nvidia/nemotron-3.5-lightning-30b-a3b`. |
| `credentials.json` | Downloaded Google Desktop OAuth client file, placed beside `app.py`. |
| `token.json` | Created beside `app.py` by authorization and reused/refreshed by the application. |
| `data/mailmind.db` | Automatically created SQLite database for scheduled messages and reminders. |

The AI client uses `https://integrate.api.nvidia.com/v1`. Existing process environment variables take precedence over `.env` values. The OpenAI SDK is used as the NVIDIA-compatible client; a separate OpenAI API key is not required.

`DATABASE_PATH` appears in the template but is not read by the current storage implementation: the application uses `data/mailmind.db`. Google credential/token paths are also fixed relative to the project root. No speech API key is required.

## Run the Streamlit application

The application imports packages from `src`, so include that directory in `PYTHONPATH`. Run from the repository root with the virtual environment active.

**Windows PowerShell:**

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m streamlit run app.py
```

**macOS / Linux:**

```bash
PYTHONPATH="$PWD/src" python -m streamlit run app.py
```

Open the local address printed by Streamlit. In **Compose Email**, record an instruction, select **Transcribe audio**, review the text, choose a tone, and select **Generate with AI**. Edit the resulting subject/body before selecting **Send Email** and **Confirm and send**.

The **AI Assistant** page links to existing tools; it is not a standalone conversational assistant. **Settings** is currently a placeholder.

## Gmail and Google Calendar integration

### Configure Google access

1. In a Google Cloud project, enable the **Gmail API** and, for event creation, the **Google Calendar API**.
2. Configure the OAuth consent screen. When using an external app in Testing, add the account you will authorize as a test user.
3. Create an OAuth client with application type **Desktop app**. Download its JSON file and save it locally as `credentials.json` beside `app.py`.
4. Configure the permissions used by the enabled workflows:

| OAuth scope | Application use |
| --- | --- |
| `https://www.googleapis.com/auth/gmail.send` | Confirmed sends and authorized scheduled delivery |
| `https://www.googleapis.com/auth/gmail.readonly` | Inbox reading, search, and sent-conversation inspection |
| `https://www.googleapis.com/auth/calendar.events.owned` | Event creation in the user's primary calendar |

5. Start MailMind and use the relevant feature. When authorization is needed, the app opens Google sign-in in a local browser and waits up to 120 seconds for a localhost callback. Adding a feature may request additional consent.

Gmail and Calendar share the root-level OAuth files. The flow is designed for one user with the app and sign-in browser on the same computer. To switch accounts, stop the app, remove the local `token.json`, and authorize again. Never use a Gmail password or service-account file in place of the Desktop OAuth client.

### Integration behavior

- **Inbox and search:** Messages are read without marking them read. Plain text is preferred; HTML is converted into readable text. Attachments are not displayed or analyzed.
- **Contextual replies:** Inbox replies use ordinary sending with a `Re:` subject; placement in the original Gmail thread is not guaranteed.
- **Follow-ups:** The scan checks up to 50 sent conversations from the last 90 days. A configurable day threshold defaults to three. Detection uses conservative response-request rules and can miss implicit requests; a qualifying reply from any recipient marks the conversation Replied. Confirmed follow-ups recheck the conversation and use the original thread and message headers, sending to the first non-self To recipient.
- **Calendar:** In Inbox, select **Extract Actions**, then **Add to Calendar** for an action. Review the title, description, start, and end before **Confirm & Add to Calendar**. Missing end times must be supplied. Events use the computer's local timezone and invite no guests. Stable event IDs help recover uncertain creation attempts without creating another event.

## Local Faster-Whisper speech recognition

The voice service loads the English `base.en` model on the CPU with `int8` computation, caches one model instance per process, and transcribes audio with English language selection and voice activity detection. The model downloads on first use and can then perform transcription locally using the cached model files.

Recordings are processed from in-memory audio buffers; the voice service does not upload audio to a speech provider. Transcribed text is editable before use. If you request AI drafting, that text is sent to NVIDIA NIM. The current voice workflow covers composition and search; spoken inbox playback and multilingual transcription are not implemented.

## Scheduling and reminder behavior

- **Scheduled emails:** Selecting **Schedule email** authorizes future automatic delivery. A background worker checks every 15 seconds while the app process runs. Keep the computer awake and establish Gmail authorization before relying on scheduled delivery. Pending messages survive restarts; overdue messages are processed when the app resumes.
- **Delivery safeguards:** SQLite atomically claims due messages before sending. Failed attempts are not automatically retried; interrupted Sending records become Failed after 15 minutes. Pending messages can be cancelled before they are claimed. Check Gmail Sent after uncertain delivery before creating a replacement.
- **Reminders:** Records persist in SQLite and support completion and deletion. Dashboard alerts refresh every 15 seconds while that page is open. Dismissal is stored persistently without completing the reminder. Notifications are in-app only.
- **Extracted actions:** Reminder creation opens a review form and saves only after confirmation. Missing dates/times require user input. Relative dates are interpreted against the source email's received date; review inferred dates and convert any stated timezone to the computer's local time. Reminder duplicate-submission guards are session-based, so check existing records after restarting.

Schedule and reminder times are stored as Unix timestamps and displayed in local time. Follow-up timestamps are displayed in UTC.

## Testing

Install the development dependencies and run the existing suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

`pytest.ini` adds `src` to the test import path. The suite includes tests for transcription validation/model configuration, AI response parsing, Gmail operations and OAuth, composition and replies, search, scheduling, reminders, priority classification, action extraction, action-to-reminder flows, Calendar creation, follow-ups, and UI/theme behavior.

Provider-facing tests use mocks, storage tests use temporary databases, and UI tests use Streamlit AppTest. These checks do not establish live provider availability or real model accuracy. No test pass count or coverage percentage is claimed here.

For a local smoke test, transcribe a short recording, review an AI draft, refresh Inbox, try search and analysis, and create a local reminder. Confirm a real email send, scheduled delivery, or Calendar event only when you intend that action. Verify the result in Gmail or Calendar as appropriate.

## Security and privacy

- `.gitignore` excludes local environment files, OAuth credentials/tokens, database files, and other secret-file patterns. Keep these files private; ignoring a file does not remove it from existing Git history.
- OAuth tokens and the SQLite database are not encrypted by the application. Protect the project directory with operating-system permissions. Scheduled records contain message content, and reminder records may contain email-derived details.
- Speech recognition is local, but AI features send the relevant instructions or email text/context to NVIDIA NIM. Gmail and Calendar operations communicate with Google. The application is not fully offline.
- Email bodies and AI output are rendered as text in inbox workflows. HTML email is converted to text without loading remote images or executing scripts.
- AI summaries, replies, classifications, and extracted dates require human review. Several analysis paths limit email bodies to the first 16,000 characters; attachments and omitted content may contain additional context.
- Immediate emails, replies, follow-ups, and Calendar creation require confirmation. Scheduled delivery runs automatically after the user authorizes the schedule. Uncertain sends are not automatically replayed.
- The current application targets local, single-user operation and does not provide a multi-user authentication or deployment model.

## Future enhancements

Potential extensions, not current features:

- Multilingual transcription and spoken email playback.
- A functional Settings page and standalone conversational assistant.
- Thread-aware sending for contextual Inbox replies.
- Broader, paginated follow-up scanning and improved implicit-request detection.
- Cross-session deduplication when creating reminders from extracted actions.
- A separately managed scheduler and notification channels that work when the Streamlit app is closed.

## Author

**ilakkiya391** — project author, as recorded in the repository's Git history.
