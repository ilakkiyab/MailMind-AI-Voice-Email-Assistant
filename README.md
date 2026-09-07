# AI Voice-Powered Email Assistant

A modular final-year software engineering project for building a voice-driven,
AI-assisted email and calendar workflow. Phase 4A adds Gmail inbox reading to
the existing local transcription, NVIDIA NIM drafting and confirmed Gmail sending.
Scheduled sending, inbox AI summaries and contextual replies are available.
Smart reminders, voice email search, priority classification and action extraction
are available, including reviewed Google Calendar event creation from extracted actions.

## Scheduled Emails

Open **Scheduled Emails**, enter a valid recipient, nonempty subject and body,
and a future date/time, then select **Schedule email** to authorize automatic
delivery through the existing Gmail sender. Times use this computer's local
timezone (including its rules for the selected date); storage uses UTC timestamps
in `data/mailmind.db`. This is a local, single-user app using the connected Gmail
account. Configure Gmail as described below before scheduling.

A background worker starts with MailMind and checks every 15 seconds on every
page, independently of browser interaction. Keep the app process running and the
computer awake. Pending messages survive restarts; overdue messages are processed
when the app starts again. The schedule list refreshes every 15 seconds while open.
Cancel pending messages or delete Sent, Cancelled and Failed records on this page.
Cancelling is unavailable once delivery has been claimed.

SQLite atomically claims each due message before sending, preventing concurrent
workers or reruns from sending it twice. Success becomes **Sent**. Failures become
**Failed** without automatic retry. Interrupted **Sending** records become Failed
after 15 minutes. A crash after Gmail accepts a message can leave delivery uncertain;
check Gmail Sent before manually scheduling a replacement. This favors at-most-once
attempts over automatic retries. Error records exclude raw provider exceptions.

Manual check: schedule a message to your own address a minute or two ahead, leave
MailMind running, and verify Sent plus Gmail delivery. Create another message and
cancel it before its due time, then delete its record. Restart the app before a
pending message is due to verify persistence. Invalid addresses, empty fields and
past times should show errors without creating records.

Focused tests (mocked Gmail, temporary SQLite files):
`python -m pytest tests/test_scheduling.py -q`. Full regression suite:
`python -m pytest tests -q`.

## Planned capabilities

- Voice-based email composition, inbox reading, and search
- AI summarization, contextual replies, tone control, and priority classification
- Scheduled sending, reminders, and unanswered-email follow-up detection
- Meeting, deadline, and task extraction
- Google Calendar event creation
- Confirmation before sending, deleting, or scheduling
- Future multilingual voice support

## Technology stack

- Python
- Streamlit
- faster-whisper (local speech recognition)
- Gmail API
- Google Calendar API
- SQLite

## Project structure

```text
AI-voice-Email-Assistant/
├── app.py                  # Streamlit entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Safe configuration template
├── .gitignore              # Excludes secrets, local data, and generated files
├── README.md               # Project documentation
├── src/
│   └── email_assistant/
│       ├── ai/             # NVIDIA NIM-backed language features
│       ├── calendar/       # Google Calendar integration
│       ├── core/           # Configuration and shared application concerns
│       ├── email/          # Gmail operations and email workflows
│       ├── models/         # Domain models and data-transfer objects
│       ├── reminders/      # Reminder and follow-up logic
│       ├── scheduling/     # Scheduled email workflows
│       ├── storage/        # SQLite access and repositories
│       ├── ui/             # Streamlit application, pages, and theme
│       └── voice/          # Speech input and output services
├── data/                   # Local runtime data (databases are ignored)
├── tests/                  # Automated tests mirroring application modules
└── docs/                   # Design, API, and project documentation
```

Each application area is isolated behind its own package so it can be built and
tested independently. External services belong in `email`, `calendar`, and `ai`;
business workflows belong in `scheduling` and `reminders`; persistence stays in
`storage`; and Streamlit-specific code stays in `ui`.

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the application:

   ```bash
    streamlit run app.py
    ```

Copy `.env.example` to `.env`, set `NVIDIA_API_KEY` there (and optionally change
`NVIDIA_MODEL`), then open the Compose Email page. Record an instruction, select
**Transcribe audio**, review or edit the returned text, choose a tone, and select
**Generate with AI**. The generated subject and body remain editable.

Speech-to-text runs locally on the CPU
using the English `base.en` model with int8 computation. The model downloads
automatically on first use and is reused for later transcriptions in the same
app process. No speech-to-text API key is required. AI drafting uses NVIDIA's
hosted OpenAI-compatible API at `https://integrate.api.nvidia.com/v1` and defaults
to `nvidia/nemotron-3.5-lightning-30b-a3b`. Credentials are read only from environment
configuration. Gmail sending is configured separately below.

## Phase 3: configure Gmail manually

1. In your Google Cloud project, enable the Gmail API.
2. Configure the Google OAuth consent screen. For an external app in Testing,
   add your Gmail account as a test user. Request only
   `https://www.googleapis.com/auth/gmail.send`.
3. Create an OAuth client with application type **Desktop app**, download its
   JSON file, and save it as `credentials.json` beside `app.py`. Do not use a
   service account or enter your Gmail password anywhere in this project.
4. If the API and Desktop client are already configured and `credentials.json`
   is in the project root, no additional credential configuration is needed.
   Gmail always uses this root-level file and saves `token.json` beside it,
   independently of the working directory. Both files are ignored by Git.
   Old `GOOGLE_CLIENT_SECRETS_FILE` and `GOOGLE_TOKEN_FILE` settings are unused.
5. Install the updated requirements and run Streamlit locally. In Compose Email,
   enter one recipient address, a subject and a body. Select **Send Email**, review
   the exact preview, then select **Confirm and send**. **Cancel send** discards
   the pending confirmation. To edit a pending message, cancel first, edit, and
   select Send Email again.
6. On first confirmed send, Google sign-in opens in your local browser. Approve
   within two minutes. The loopback callback uses a temporary localhost port.
   After authorization, the confirmed message is sent and the UI displays
   **Email sent successfully**.

This OAuth flow is for one user running Streamlit and the browser on the same
computer, not a shared or remotely hosted deployment. The saved token represents
the sending Gmail account and is reused/refreshed on later sends. Invalid or
revoked refresh tokens trigger sign-in again. To switch accounts, stop the app,
remove the project-root `token.json`, then authorize
again. Protect local token files with your OS account permissions; they are not
encrypted by the application. Testing-mode Google grants may expire and require
fresh authorization.

Missing credentials, rejected authorization, invalid addresses and API/network
errors produce messages in the UI. Address validation checks syntax, not mailbox
existence. Failed sends retain your draft but require a fresh confirmation.
Delivery is never automatically retried: after an uncertain network/server result,
check Gmail Sent before resending to avoid duplicates.

Google documentation: [Python OAuth quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
and [sending messages](https://developers.google.com/workspace/gmail/api/guides/sending).

## Phase 4A: read your Gmail inbox

1. Keep the existing Desktop OAuth client and `credentials.json`. Add
   `https://www.googleapis.com/auth/gmail.readonly` to your Google OAuth consent
   configuration alongside the existing `gmail.send` permission.
2. Run `streamlit run app.py` and select **Inbox**. The first visit with a
   send-only token opens the existing Google sign-in flow to request both
   permissions. Approve within two minutes. The same `token.json` is updated;
   subsequent sending reuses it without losing sending permission.
3. Check the latest ten inbox messages for sender, subject, received time
   (in this computer's time zone), and preview. Expand **Read email** to see the
   body. Plain text is preferred; HTML is converted to text without loading
   remote images or running scripts. Attachments are not displayed.
4. Select **Refresh Inbox** after receiving a new message. Messages are kept
   only in the current Streamlit session, and reading does not mark them read.
   Test with plain-text, HTML-only and multipart messages.
5. An empty inbox displays a friendly notice. Network/API errors offer a retry;
   expired tokens are refreshed through the existing authentication system,
   and revoked refresh tokens trigger sign-in again. If Gmail rejects a cached
   authorization, remove only local `token.json`, then refresh and authorize again.

No additional dependencies are needed. Gmail API details:
[listing messages](https://developers.google.com/workspace/gmail/api/guides/list-messages)
and [message content](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages).

## AI email summarization

In **Inbox**, click **Summarize with AI** beneath any message to show a short
summary in place, with 2–4 requested bullet points covering key facts and actions.
This sends that email's readable body to the same NVIDIA provider used for drafting,
using the existing `NVIDIA_API_KEY` and optional `NVIDIA_MODEL`; no new key is needed.
Summaries remain in the current session until **Refresh Inbox**. HTML is converted
to text; bodies longer than 16,000 characters use the first 16,000 with a visible
notice. Read the full email for omitted details. Empty bodies and provider failures
show safe messages; click again to retry. Attachments are not summarized.

## AI Email Priority Classification

In **Inbox**, click **Check Priority** under an email to display 🔴 High Priority,
🟡 Medium Priority or 🟢 Low Priority and a short reason. Only clicks call the
existing NVIDIA provider, using the same `NVIDIA_API_KEY` and `NVIDIA_MODEL`.
Classification considers urgency, deadlines, interviews, jobs, meetings, exams,
security warnings and requested actions versus ordinary updates and promotions.
Results stay associated with each Gmail message throughout the Streamlit session,
including refreshes. Click again to reassess; empty content and AI failures show
friendly retry guidance. Long bodies use the first 16,000 readable characters with
a visible notice; attachments are not analyzed.

Focused tests: `python -m pytest tests/test_priority.py -q`.

## AI Action & Deadline Extraction

In **Inbox**, click **Extract Actions** beneath an email to display **Action &
Deadline Analysis**. Each detected meeting, interview, appointment, task, document
submission or deadline appears separately with action, type, date, time and
description. Emails without actions show “No actions or deadlines detected in this
email.” Missing dates/times show **Not specified**.

Extraction uses the existing NVIDIA provider, `NVIDIA_API_KEY` and optional
`NVIDIA_MODEL`, and runs only on a click. The email's subject and readable body
are sent with its received timestamp in the computer's local timezone. Relative
dates use that received date, never today's date. Tomorrow is the following day;
next Monday is the next strictly future Monday; this Friday is Friday of the
received date's Monday–Sunday week. Inferred dates (including resolved omitted
years) are labeled separately from explicit full dates. Unclear dates remain
unresolved. Original time wording preserves any stated timezone without assuming
an event timezone. Source excerpts are displayed for review.

Internally, validated JSON becomes immutable action records with nullable ISO
date and 24-hour time, title, type, description, date provenance and source text.
The analysis retains the source message ID and received timestamp. Each action's
**Create Reminder** button opens an editable review form using the existing Smart
Reminder service and storage. Review the title, description, date and time, then
click **Confirm Reminder** to save. Nothing is saved by extraction or by opening
the form. The description includes only the action description, email subject
and sender, without copying the email body or source excerpt.

Resolved dates and available times are pre-filled; missing or invalid values stay
blank and must be selected. Dates/times must be in the future. Reminder times use
the computer's local timezone: review the original time wording and adjust for
any different timezone before confirming. AI interpretation still needs review
against the source email before use.

Draft edits and successful submission guards are isolated by email and action in
the current Streamlit session, including when emails/actions reorder or their
widgets are hidden. A successful submission shows **Reminder created successfully.**
and **View Reminders** opens the existing Reminders page. Reruns cannot submit the
same successful draft again; storage failures preserve edits for retry. This is
a session guard, not cross-session action deduplication: after restarting the
session, check existing Reminders before creating the same action again.
Google Calendar is not integrated, and this flow does not change Gmail data.

Focused integration tests: `python -m pytest tests/test_action_reminders.py tests/test_actions.py tests/test_reminders.py -q`.

Results stay keyed by Gmail message ID in the current Streamlit session, including
inbox refreshes and reordering. Click again to reanalyze; a failed retry retains
the previous result. Empty content, missing configuration, authentication,
quota/rate limits, network errors and malformed responses show friendly errors.
Long messages use the first 16,000 readable body characters and 2,000 subject
characters with a visible notice; attachments are not analyzed.

Focused tests (mocked AI and inbox): `python -m pytest tests/test_actions.py -q`.
Manual check: extract from a deadline email, a meeting with date/time, and an email
with multiple actions; then try an informational email and a task without a date.
Extract from two different messages, refresh the inbox, and verify each result
remains below its source. Check a relative date against that email's received date.

## Contextual AI replies

In **Inbox**, choose Professional (default), Friendly, Formal, or Concise and
click **Generate AI Reply** under an email. Its sender, subject and readable body
are sent to the same NVIDIA client, `NVIDIA_API_KEY` and `NVIDIA_MODEL` used by
drafting and summaries. Each message keeps its own editable reply in the current
session, including across inbox refreshes. **Regenerate Reply** replaces that
draft; **Clear Reply** removes it. Generation failures retain your previous edits.

Review all facts before sending: AI is instructed to avoid invented facts and
commitments, but output still needs human review. **Send Reply** displays the exact
recipient, subject and edited body; **Confirm and send reply** performs delivery
through the existing Gmail OAuth/sending service. Nothing sends automatically.
Replies go to the original From address with a `Re:` subject (without duplicating
an existing prefix). This uses ordinary sending, without Gmail `threadId`,
`In-Reply-To` or `References`: original-thread placement is **not guaranteed**.

Empty bodies show guidance without calling AI. HTML becomes readable text, and
long bodies use the first 16,000 readable characters with a visible warning.
Sender/subject context is bounded to 1,000/2,000 characters. Attachments are not
included. Heuristic no-reply/newsletter warnings cannot identify every automated
sender; verify the recipient. Configuration and network failures show safe retry
guidance. After uncertain delivery, check Gmail Sent before trying again.

## Smart Reminders

Open **Reminders**, enter a title, optional description, date and time, then select
**Create reminder**. Choose a future time in this computer's local timezone, as
with Scheduled Emails. View **Upcoming**, **Past/Overdue**, and **Completed**
sections; use **Mark as completed** or **Delete reminder** to manage records.

Reminders persist in the separate `reminders` table in `data/mailmind.db`, with
scheduled times stored as Unix timestamps and displayed in local time. While
MailMind is open and the computer is awake, every page checks for due reminders
every 15 seconds. Due notifications stay visible until dismissed, completed or
deleted. Dismissal prevents repeat notifications in the same Streamlit session;
a new session can notify again about still-pending overdue reminders, including
ones missed while the app was closed. Reminders only show in-app notifications
and never send email. No additional credentials or dependencies are needed.

## Voice Email Search

Open **Voice Email Search** from the sidebar or the dashboard's Voice Search card.
Type a query, or record one and select **Transcribe search query**. Review/edit
the text, then click **Search Emails**. Examples: “Find emails from Google”,
“Find emails from Unstop”, “Show emails about placement”, “Show emails containing
interview”, and “Find emails about assessment”. Explicit Gmail syntax also works.
**Clear Search** clears the query, recording and results.

Search reuses the existing local Faster-Whisper model and Gmail OAuth setup with
the same inbox read-only permission. Up to 20 matching inbox messages appear with
sender, subject, local received time, preview and expandable readable body.
Searching does not mark messages read. Empty results and authentication/network
errors show friendly guidance. Results stay in the current session; no new
dependencies or credentials are needed.

Focused tests: `python -m pytest tests/test_search.py -q` (mocked Gmail and voice).

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
python -m compileall -q src app.py tests
```

Gmail and Compose tests mock OAuth and delivery; they do not open authorization
or send real email. A real end-to-end send requires your manual Google setup.

## Security

Do not commit API keys, OAuth client-secret files, access tokens, or local
databases. The supplied `.gitignore` excludes these files, and `.env.example`
contains names and safe placeholder paths only.

## Google Calendar from extracted actions

**Where is Add to Calendar?** Click **Extract Actions** on an individual Inbox
email, then look below each detected action, after **Create Reminder**. The button
appears for every extracted Meeting, Interview, Appointment, Deadline, Task,
Document Submission, Payment Deadline, or Application Deadline. Missing dates or
times do not hide it; you enter those in the review. It does not appear when
extraction returns no actions or fails. API enablement/OAuth is checked only when
you confirm creation, not when displaying the button. A successfully added action
shows its success message instead of another Add button.

For a manual test, use a new email in the latest ten Inbox messages with subject
`Project review meeting` and body `Please attend the project review meeting on
15 October 2026 from 10:00 AM to 11:00 AM IST. We will review the project demo.`
Use a future date if that date has passed. Expect a Meeting action and the button
directly below it. Newsletters, completed security updates, and informational
course announcements are not reliable tests because they may contain no action.

1. In the **same Google Cloud project** as the existing `credentials.json`, open
   **APIs & Services → Library → Google Calendar API → Enable**.
2. Keep the existing Desktop OAuth client, `credentials.json`, and `token.json`.
   In Google Auth Platform / OAuth consent configuration, add
   `https://www.googleapis.com/auth/calendar.events.owned` to Data Access if needed.
   Keep your Google account on the test-user list while the app is in testing.
   This is the narrowest events scope supporting creation on your owned primary
   calendar; Google does not offer a create-only primary-calendar scope.
   See [Google's events.insert reference](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert).
3. Start the existing app normally. Open **Inbox → Extract Actions → Add to Calendar**.
   Review title, description, source subject/sender, date, start time, end date/time.
   Missing dates/times remain blank. Explicit end times/durations are prefilled;
   otherwise choose the end time yourself. All entered times use the computer's
   local timezone: convert any different timezone stated in the email before confirming.
4. Select **Confirm & Add to Calendar**. On first use, the existing OAuth flow
   requests Calendar permission and preserves the Gmail scopes already in the token.
   Choose the **same Google account as Gmail** and grant the requested permissions.
   Cancelled or incomplete consent does not overwrite the existing token.
   Valid tokens are reused and expired tokens use the existing refresh path.
5. Look for **Event added to Google Calendar**, then use **Open event in Google Calendar**
   and verify the event in that account's primary calendar. **Cancel** creates nothing.

No guests are invited and no Gmail data is changed by Calendar creation. Each
email/action has its own editable session draft. A stable Google event ID protects
reruns, double clicks, and retries after a network timeout (including a new session
with the same extracted action). Re-extraction that materially changes an action
creates a new identity, so check Calendar before adding a changed extraction again.
After an uncertain attempt, retry with the original submitted details; changing
those details is blocked to avoid misreporting an existing event. Edit an already
created event directly in Google Calendar. Draft edits live only in the current session.

If the API is disabled, enable it in the credentials' project. If permission is
missing, retry and grant Calendar access. For revoked/invalid tokens, retry OAuth;
if a valid-looking token repeatedly gets a 401/403, stop the app, securely remove
local `token.json`, restart and authorize Gmail and Calendar again (never remove
`credentials.json`). This also requires Gmail re-consent. Keep all OAuth files private.
Network failures preserve the draft; retrying the same action uses the same event ID.

Tests use synthetic emails, temporary OAuth files, and mocked Calendar services:
`python -m pytest tests/test_calendar.py tests/test_actions.py tests/test_action_reminders.py tests/test_email.py -q`.
No real Google Calendar event is created by these tests. Live integration is only
verified after you manually see the event in your Google Calendar.

## AI Follow-up Detection

Open **Follow-ups** in the sidebar. MailMind reuses Gmail OAuth (send and read-only
permissions, preserving existing Calendar permissions) to scan up to 50 recent
Sent conversations from the last 90 days without marking mail read. Select
**Refresh Follow-ups** for a new scan. The editable threshold defaults to **3 days**
and is retained for the current session.

Each relevant thread has one entry showing recipient(s), subject, UTC sent date,
whole days waiting, message/thread IDs, and **Follow-up Needed**, **Replied**, or
**Waiting**. Waiting starts at the latest sent message; a later reply from any To
recipient marks the thread Replied. Self-sent messages and sender aliases observed
in Sent are not recipient replies. Automated/list headers, no-reply addresses,
newsletters and obvious FYIs are excluded. Detection uses conservative English
request/question rules (not an AI classification call); implicit requests and
other languages may be missed. Replies in separate threads cannot be detected.
CC-only replies are not counted. This is a bounded scan, not a complete mailbox audit.

For a flagged email, **Generate Follow-up** uses the existing NVIDIA provider and
model configuration to write a short professional draft. Only that email's context
(up to 16,000 body characters) is sent to the AI provider. Drafts are editable and
isolated by account, thread and source message in the current session.
**Send Follow-up** shows the exact recipient, subject and body for review; only
**Confirm and send follow-up** sends. **Cancel** sends nothing, and editing invalidates
confirmation. Sending targets the first external To recipient and uses the original
Gmail thread, In-Reply-To and References headers. Missing original message headers
block delivery. Confirmation rechecks the conversation before sending; a reply or
newer sent message blocks stale delivery. A reply arriving after that check is still
possible. No background follow-up emails are sent. Successful sends are guarded
against repeat clicks for the current source message. On uncertain delivery, check
Gmail Sent before retrying; sending is never automatically retried.

Gmail lookup failures discard incomplete scans instead of guessing reply status.
AI failures preserve existing edits. Drafts and preferences are session-only.
The existing Faster-Whisper implementation is unchanged.

### Manual testing

1. Start the app using your normal environment: `python -m streamlit run app.py`.
2. Open **Follow-ups**, authorize the existing Gmail account if prompted, and
   select **Refresh Follow-ups**. Verify the displayed IDs, recipients, subjects
   and UTC dates against Gmail Sent.
3. Locate an existing response-requesting sent email older than three days with
   no reply. Verify **Follow-up Needed**. Increase the threshold above its days
   waiting and verify **Waiting**; lower it back and verify it is flagged again.
4. Check an existing thread with a later recipient reply: expect **Replied**.
   Check a thread with only your own later sent messages: expect a waiting period
   based on your latest sent message, not Replied. Verify multiple sent messages
   produce only one entry. Check newsletters, no-reply mail and FYIs are excluded.
5. Generate drafts for two flagged threads. Edit one, switch pages and return.
   Verify each draft remains under its own email. Select **Send Follow-up** and
   inspect the preview; verify nothing appears in Gmail Sent yet. Select **Cancel**.
6. Select Send again, edit the draft and verify confirmation disappears. Select
   Send again to review the edited text. To test actual delivery, use only a
   recipient you control and explicitly select **Confirm and send follow-up**.
   Verify exactly one sent message in the original Gmail thread, then refresh
   Follow-ups and verify the waiting period resets. Skip confirmation to test
   the entire draft workflow without sending any email.
7. If the recipient replies after opening the preview, confirming should block
   stale delivery and request a refresh. Try a disconnected network during refresh
   or generation: expect an error message, not an app crash.
8. Smoke-test Compose, Inbox, voice transcription, scheduling, reminders, priority,
   action extraction and Calendar using your usual workflows. Avoid confirming any
   real send or Calendar creation unless you intend that external action.

Automated tests use synthetic mail and mocked Gmail/AI services; no real emails
are sent. Focused: `python -m pytest tests/test_followups.py tests/test_email.py tests/test_replies.py -q`.
Full regression: `python -m pytest tests -q`.
