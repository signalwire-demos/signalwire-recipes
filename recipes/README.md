# Recipes

Every folder here is self-contained. Clone the repository, open one, and run it.

121 recipes, each proved by its own verifier.

Each recipe proves one claim about the platform. Its `verify.py` checks that claim
against the document the platform actually receives, so it runs without an account
and without a network.

## Contents

- [AI Agents](#ai-agents) (42)
- [Voice](#voice) (57)
- [Messaging](#messaging) (12)
- [MFA](#mfa) (1)
- [Video](#video) (5)
- [Fax](#fax) (2)
- [Builds](#builds)

## AI Agents

Agents that answer, reason, and act on a live call.

### Call control

| Recipe | What it shows | Runs as |
|---|---|---|
| [Control when a caller can interrupt a voice AI agent](control-when-a-caller-can-interrupt-a-voice-agent/) | Set which speech events may cut a voice AI agent off, how many words it takes, and how much silence ends the caller's turn, as bounded ai.params. | Python, TypeScript |
| [Pause a voice AI agent mid-call and bring it back](pause-a-voice-ai-agent-mid-call/) | Put the caller on hold with a spoken line, take them off it, or end the AI on a call that keeps running, each with one REST command. | Python, TypeScript |
| [Place an outbound AI call](place-an-outbound-ai-call/) | Place a REST call with the voice AI agent definition and wait for the callee to speak before the agent responds. | Python, Markup |

### Governance

| Recipe | What it shows | Runs as |
|---|---|---|
| [Collect required details in any order with a voice AI agent](collect-required-details-in-any-order/) | Let a caller give the required details of a report in any order, keep the checklist in the tool handlers, and refuse to file until every required detail is in. | Python, TypeScript |
| [Control which tools an AI agent can call at each step](scope-tools-per-step/) | At each point in the conversation the model can only see the tools you allowed there. | Python |
| [Enforce an AI agent's next step in code](enforce-state-transitions-in-a-tool-handler/) | Return the next allowed conversation state from code instead of letting the AI agent choose it. | Python |
| [Get recording consent before recording](get-recording-consent-before-recording/) | Speak the disclosure and capture the answer before any audio is written to disk. | Python |
| [Keep per-call state server-side, keyed by call id](keep-heavy-state-out-of-global-data/) | Store full per-call state on your server, keyed by call ID, and expose only the fields the voice AI agent needs. | Python |
| [Protect AI agent tool webhooks with per-call tokens](protect-tool-webhooks-with-per-call-tokens/) | Mint a token for each call and AI agent tool, then reject missing, expired, edited, or mismatched tokens. | Python |
| [Require verification before unlocking AI agent tools](require-verification-before-unlocking-tools/) | The account tools do not exist in the model's world until a handler says the caller passed. | Python |
| [Run isolated personas behind one number](split-one-number-into-isolated-personas/) | Route one phone number among isolated sales, support, and billing AI personas, each with access only to its own tools. | Python |
| [Show the AI model only the fields it needs](hide-fields-from-the-model/) | Load the whole record, expose a curated slice, and keep the rest out of the prompt entirely. | Python |
| [Walk a caller through steps they cannot skip](walk-a-caller-through-ordered-steps/) | Expose only the next allowed AI agent tool at each step so callers cannot move backward or skip ahead. | Python |
| [Write call dispositions from data your handlers recorded](write-a-disposition-from-handler-owned-data/) | Build call dispositions only from qualification fields recorded by tool handlers, not from transcripts or model summaries. | Python |

### Handoff

| Recipe | What it shows | Runs as |
|---|---|---|
| [Change a voice AI agent's instructions mid-call](change-the-agents-instructions-mid-call/) | A tool result replaces the system prompt on the call in progress, summarising or dropping the earlier turns, with no transfer. | Python |
| [Transfer a call without losing context](transfer-a-call-without-losing-context/) | Pass caller identity and state with the transfer so the next call leg receives the context. | Python |

### Knowledge

| Recipe | What it shows | Runs as |
|---|---|---|
| [Ground a voice AI agent in your documents](ground-an-agent-in-your-docs/) | Connect a voice AI agent to your documents so it retrieves relevant content before answering. | Python |
| [Remember a returning caller across calls](remember-a-returning-caller-across-calls/) | Have the platform save a summary when a call ends and hand it back when the same number calls again, so the agent picks up where it left off. | Python, TypeScript |

### Monitoring

| Recipe | What it shows | Runs as |
|---|---|---|
| [Inject a message into a live AI call](inject-a-message-into-a-live-ai-call/) | Send a REST command to update a live AI call with a system message, shared data, or a replacement prompt. | Python |
| [Stream voice AI agent debug events](stream-agent-debug-events/) | Select a voice AI debug level, stream matching events to your webhook, and handle them as they arrive. | Python, Markup |
| [Test a voice AI agent offline with swaig-test](test-an-agent-offline-with-swaig-test/) | The SDK's swaig-test command loads an agent file with no number, tunnel or account. It prints the SWML the platform would fetch, lists the tools, and runs any tool with the arguments you give it. | Python |

### Routing & queueing

| Recipe | What it shows | Runs as |
|---|---|---|
| [Give an AI agent a SIP address](give-an-ai-agent-a-sip-address/) | Create a SIP address that rings a hosted AI agent, so a SIP phone or PBX can reach it without a phone number in between. | Python, TypeScript |
| [Route a call to an AI agent](route-a-call-to-an-ai-agent/) | Point a phone number at an agent and let it answer. | Python, TypeScript |

### Tools & integrations

| Recipe | What it shows | Runs as |
|---|---|---|
| [Commit a transaction from a call](commit-a-transaction-from-a-call/) | Use an allow-list to validate the caller's confirmation before one transaction tool commits the request. | Python |
| [Cover AI agent tool latency with fillers](cover-tool-latency-with-fillers/) | Play localized filler phrases or a hosted wait file while a slow AI agent tool finishes. | Python |
| [Create a hosted voice AI agent with one REST call](create-a-hosted-voice-ai-agent-with-one-rest-call/) | Turn the agent definition you would serve yourself into a resource SignalWire hosts, with one POST, then put a phone number on it with one more. | Python, TypeScript |
| [Extract structured data after a call](extract-structured-data-after-a-call/) | Get typed fields out of a finished conversation instead of parsing a transcript. | Python |
| [Give a voice AI agent a tool](give-an-agent-a-tool/) | Let the model call your function, and decide what it gets back. | Python, TypeScript |
| [Let a browser dial your agent with no dashboard setup](let-a-browser-dial-your-agent-with-no-dashboard-setup/) | Create a dialable voice AI endpoint and a restricted guest token over REST, without configuring either in the dashboard. | Python |
| [Let a voice AI agent call an API without your server](call-an-api-without-a-backend/) | SignalWire makes the API call, so no service of yours is in the tool path. | Python, Markup |
| [Let a voice AI agent see the caller's camera](let-an-agent-see-the-callers-camera/) | Enable visual input, choose a vision model, and play a filler while the voice AI agent analyzes the caller's camera. | Python |
| [Normalize spoken dates and phone numbers in a voice AI tool handler](normalize-spoken-dates-and-phone-numbers-in-a-tool-handler/) | Take a date and a phone number in the caller's words, turn them into an ISO date and an E.164 number in the tool handler, and read both back for the caller to check. | Python, TypeScript |
| [Push events from a voice AI agent to the browser](push-events-from-an-agent-to-the-browser/) | Return a JSON event from a voice AI agent tool and deliver it to the browser connected to the call. | Python, Markup |
| [Write a reusable AI agent skill](write-a-reusable-agent-skill/) | Package a capability once and load it into any agent with one line. | Python |

### Other

| Recipe | What it shows | Runs as |
|---|---|---|
| [Configure a voice AI agent per request for many tenants](configure-an-agent-per-request/) | Configure a temporary voice AI agent for each request from tenant data in a query string or header, without changing the deployed agent. | Python |
| [Give a voice AI agent a video avatar](give-an-agent-a-video-avatar/) | Assign idle, listening, and talking video files so a voice AI agent shows the matching avatar state during video calls. | Python, Markup |
| [Run LiveKit Agents code on SignalWire](run-livekit-agents-code-on-signalwire/) | Run LiveKit Agents-style instructions, sessions, and Python tools through SignalWire while keeping the same agent structure and tool functions. | Python |
| [Run a Bedrock voice agent](run-a-bedrock-voice-agent/) | Run the same voice AI agent and tool handler through Amazon Bedrock by changing the agent class and Bedrock settings. | Python |
| [Run a voice AI agent as an AWS Lambda function](run-an-agent-as-a-cloud-function/) | Deploy one voice AI agent file as an AWS Lambda handler for both call-flow and tool requests behind basic authentication. | Python |
| [Run a voice AI agent from one YAML file](run-an-agent-from-one-yaml-file/) | Define and run a voice AI agent from one YAML file without installing an SDK or hosting a server. | Markup |
| [Start from a prefab AI agent](start-from-a-prefab-agent/) | A complete receptionist or survey agent runs from a prefab class and a short configuration block. | Python, TypeScript |
| [Switch language mid-call](switch-language-mid-call/) | Change the conversation language and matching voice during a live voice AI call. | Python, Markup |

## Voice

Call control, routing, recording, conferencing, SIP, and calling from the browser.

### Call control

| Recipe | What it shows | Runs as |
|---|---|---|
| [Answer an inbound call](answer-an-inbound-call/) | Accept an incoming call, greet the caller, and hang up cleanly. | Python, Markup |
| [Build a conference call](build-a-conference-call/) | Put several legs in one room and control each member independently. | Python, Markup |
| [Call from a browser](call-from-a-browser/) | Place a call from a web page into the same flow a phone reaches. | TypeScript, Python |
| [Connect a PBX with a Domain Application](connect-a-pbx-with-a-domain-application/) | An IP-authenticated Domain Application takes inbound SIP from your PBX and a SIP Gateway carries calls back to it. | Python, Markup |
| [Detect a machine, fax tone or digits on a call in progress](detect-a-machine-or-fax-on-a-call-in-progress/) | Start answering machine, fax tone or keypad detection on a call that is already up, and read the result at your webhook. | Python, TypeScript |
| [Detect an answering machine](detect-an-answering-machine/) | Use answering machine detection to classify a pickup as human or voicemail before playing the main message. | Python |
| [Embed a call widget with no backend](embed-a-call-widget-with-no-backend/) | A sw-click-to-call element with a Click to Call token from the Dashboard and a destination address puts a call button on a page. No server of yours is in the call path. | Python |
| [End or transfer a live call over REST](end-or-transfer-a-live-call-over-rest/) | Hang up a live call with a reason, send it to a new destination, or unbridge it from its peer, each with one REST command addressed to the call id. | Python, TypeScript |
| [Pause and resume a call recording over REST](pause-and-resume-a-call-recording-over-rest/) | Start recording a live call from your own backend, pause it while a card number is read out, resume it, and stop it, all by control id over REST. | Python, TypeScript |
| [Place an outbound call](place-an-outbound-call/) | Dial a number from your own code and follow the call through to completion. | Python |
| [Play a prompt and collect digits or speech over REST](play-a-prompt-and-collect-input-over-rest/) | Speak a prompt into a live call from your own backend, stop it early, and collect keypad digits or speech, with the result delivered to your webhook. | Python, TypeScript |
| [Receive calls in the browser](receive-calls-in-the-browser/) | Register a browser as a WebRTC endpoint with a subscriber token, then route calls to its address. | Python, TypeScript |
| [Record a call](record-a-call/) | Start a recording and pick it up from the completion webhook. | Python, Markup |
| [Reduce background noise on a call](reduce-background-noise-on-a-call/) | Turn call noise reduction on or off in the call flow or during a live call through REST. | Markup, Python |
| [Register a SIP endpoint and receive calls](register-a-sip-endpoint-and-receive-calls/) | Create SIP credentials for a softphone, register it as an endpoint, and route calls to its address. | Python |
| [Send DTMF to someone else's IVR](send-dtmf-to-an-external-ivr/) | Send programmed keypad tones during an outbound call to navigate an external IVR. | Python |
| [Start, steer and stop live translation on a call in progress](control-live-translation-on-a-call-in-progress/) | Switch translation on partway through a call, speak a translated line into it, ask for a summary, and switch it off, each with one REST command. | Python, TypeScript |
| [Stream call audio to a WebSocket that checks a bearer token](stream-call-audio-to-an-authenticated-websocket/) | Send one side of a call, or both, to your own WebSocket over TLS, with a bearer token on the connection and your own metadata attached. | Python, TypeScript |
| [Stream call audio to your own server](stream-call-audio-to-your-own-server/) | Copy live call audio to your WebSocket or RTP server, then stop the stream by its control ID. | Markup, Python |
| [Take a voicemail](take-a-voicemail/) | If a bridge fails, play a voicemail prompt, record the caller's message, and send its download URL to a status webhook. | Markup, Python |
| [Transcribe a voicemail and text it to the owner](transcribe-a-voicemail-and-text-it-to-the-owner/) | Turn transcription on in a cXML Record, then text the owner the words and the recording link when the transcription callback arrives. | Python, TypeScript |
| [Transfer a SIP call with REFER](transfer-a-sip-call-with-refer/) | Hand a SIP call to another endpoint with a REFER, sending the destination URI and, when the far end asks for them, credentials. | Python, TypeScript |

### Governance

| Recipe | What it shows | Runs as |
|---|---|---|
| [Check consent before an outbound call](check-consent-before-an-outbound-call/) | Check stored consent and the callee's local calling window before your code sends an outbound dial request. | Python |
| [Export recordings and enforce retention](export-recordings-and-enforce-retention/) | Copy recordings older than your retention window to your storage, then delete each SignalWire original after a successful copy. | Python |
| [Isolate tenants with subprojects and scoped tokens](isolate-tenants-with-subprojects-and-scoped-tokens/) | Create a subproject for each tenant and issue API tokens limited to that subproject and an explicit permission list. | Python |
| [Issue a browser calling token restricted to chosen destinations](get-a-webrtc-token-with-restricted-dial-targets/) | Mint a short-lived browser token and restrict what it is allowed to call. | Python |
| [Let your users buy a phone number through your app](let-your-users-buy-a-phone-number-through-your-app/) | Give each customer their own project and API token, then search, buy, route and release phone numbers with their credentials rather than yours. | Python, TypeScript |
| [Register an E911 address for a number](register-an-e911-address-for-a-number/) | Create an emergency address through REST, look up the phone number, and attach that address to it. | Python |
| [Verify a caller id for outbound calls](verify-a-caller-id-for-outbound-calls/) | Three REST requests register a number you own elsewhere as a verified caller ID. You submit the code you heard, and redial the verification call if you missed it. | Python |
| [Verify a webhook signature](verify-a-webhook-signature/) | The gate refuses, with 403 and before any route runs, a request whose signature header does not match hex(HMAC(signing_key, url + raw_body)). X-Signalwire-SHA256-Signature decides when present; otherwise X-Signalwire-Signature, the SHA-1 one, does. | Python |

### Handoff

| Recipe | What it shows | Runs as |
|---|---|---|
| [Hand off from AI to a human agent](hand-off-from-ai-to-a-human-agent/) | Store the AI agent's notes by call ID, transfer the caller to a queue, and load those notes for the human agent. | Python |
| [Transfer a call](transfer-a-call/) | Move a live caller to another number or address. | Python, Markup |
| [Whisper a summary to the agent before connecting the caller](brief-the-human-before-the-bridge-completes/) | Compose a bounded summary, play it to the agent, then join the caller. | Python |

### Monitoring

| Recipe | What it shows | Runs as |
|---|---|---|
| [Barge into a live call](barge-into-a-live-call/) | Join an in-progress call with full audio, and leave without tearing it down. | Python |
| [Handle call status callbacks](handle-call-status-callbacks/) | Receive ordered webhooks for initiated, ringing, answered, and completed call states, keyed by call ID. | Python |
| [Listen to a live call](listen-to-a-live-call/) | Attach to a call in progress and hear both sides without joining it. | Python |
| [Reconcile webhooks against the Logs API](reconcile-webhooks-against-the-logs-api/) | Page through voice and message logs, find entries missing from your webhook store, and retrieve each missing call's event history. | Python |
| [Start live transcription and consume the webhook](start-live-transcription/) | Turn on transcription for a call and receive the text as it is spoken. | Python, Markup |
| [Transcribe a call in the background](transcribe-a-call-in-the-background/) | Start or stop background transcription on a live call through REST and receive available transcript text at your status webhook. | Python |
| [Whisper to an agent mid-call](whisper-to-an-agent-mid-call/) | One-way audio that only the agent's leg can hear. | Python |

### Routing & queueing

| Recipe | What it shows | Runs as |
|---|---|---|
| [Build an IVR menu](build-an-ivr-menu/) | Play a menu, collect keypad input, and route the caller to the right place. | Python, Markup |
| [Build an IVR without a server](build-an-ivr-without-a-server/) | Create and assign a serverless IVR call flow through REST, without hosting a webhook server. | Python |
| [Collect speech input and branch on it](collect-speech-input-and-branch/) | Ask an open question, recognise the answer, and take a different path for each. | Python, Markup |
| [Dial destinations in order or all at once, with a failure path](try-destinations-in-order/) | Dial destinations sequentially or simultaneously, then run a failure branch if no connection succeeds. | Markup, Python |
| [Forward calls to a phone and keep the caller's number](forward-calls-to-a-phone-and-keep-the-callers-number/) | Forward every call on a number to a phone, and show that phone the original caller's number instead of your own. | Python, TypeScript |
| [Host a TwiML bin without a server](host-a-twiml-bin-without-a-server/) | Store a cXML document on SignalWire with one REST call, get back the URL it is served from, and route a number to it, with no server of yours in the call. | Python, TypeScript |
| [Look up the caller and branch inside the call flow](look-up-the-caller-and-branch-inside-the-call-flow/) | Have the call itself fetch the caller's record from your API, branch on a field of the reply, and still reach a human when the lookup fails. | Python, TypeScript |
| [Offer a callback instead of a hold](offer-a-callback-instead-of-a-hold/) | Collect the caller's number and context, end the held call, then call them back with that context. | Python |
| [Queue a call until an agent is free](queue-a-call-until-an-agent-is-free/) | Callers wait in a named queue with hold audio and are bridged in order as agents connect to it. | Markup, Python |
| [Reject callers on a blocklist before answering](reject-callers-on-a-blocklist-before-answering/) | Read the caller's number when SignalWire fetches your call document, and decline a listed number before the call is answered while everyone else is connected. | Python, TypeScript |
| [Relay calls and texts through a proxy number](relay-calls-and-texts-through-a-proxy-number/) | Pair two people on one number of yours so calls and texts between them are relayed with your number showing, and neither ever sees the other's. | Python, TypeScript |
| [Route SIP calls to AI agents by username](route-sip-calls-to-agents-by-username/) | Map SIP usernames on one domain to different AI agents and return the selected agent's call flow. | Python |
| [Route calls by dialed number or time](route-calls-by-dialed-number-or-time/) | Read the dialed number and local time from each inbound webhook, then return the matching call flow. | Python |

### Other

| Recipe | What it shows | Runs as |
|---|---|---|
| [Buy a number and point it at your app](buy-a-number-and-point-it-at-your-app/) | Search by area code or pattern, purchase, and assign the number's call and message handlers, all over REST. | Python |
| [Look up a caller's carrier and name](look-up-a-callers-carrier-and-name/) | One GET returns a number's validity, formatting, country and type. include=carrier,cnam adds the carrier record and the caller-ID name. | Python |
| [Move a TwiML app by changing the endpoint](move-a-twiml-app-by-changing-the-endpoint/) | Point your TwiML app at SignalWire's compatible REST endpoint and credentials while keeping the same call request and XML response. | Python |
| [Translate a call in real time](translate-a-call-in-real-time/) | Translate both sides of one bridged call so each participant speaks and hears their chosen language. | Python, Markup |

## Messaging

SMS, MMS, and chat on the same agent.

### Call control

| Recipe | What it shows | Runs as |
|---|---|---|
| [Call the recipient when a text goes undelivered](call-when-a-text-goes-undelivered/) | Turn an undelivered or failed message status callback into one outbound call that speaks the same message, once per message and only when SignalWire signed the callback. | Python, TypeScript |

### Governance

| Recipe | What it shows | Runs as |
|---|---|---|
| [Handle SMS STOP and START in your own code](handle-opt-outs-yourself/) | Verify inbound webhook signatures, record STOP or START, send a confirmation, and check the consent record before every outbound SMS. | Python |
| [Redact a message body after sending](redact-a-message-body-after-sending/) | One PATCH with body "" clears a sent message's stored body in SignalWire's records. The empty string is the only value the spec accepts, and only a message in a terminal state is eligible. | Python |
| [Register a 10DLC brand and campaign](register-a-10dlc-brand-and-campaign/) | A brand and campaign are registered over REST, numbers are assigned to the campaign, and the status webhook reports carrier approval. | Python |
| [Send a batch within your rate limit](send-a-batch-within-your-rate-limit/) | Start one SMS request per documented interval for the number type while leaving carrier delivery timing to the platform. | Python |

### Routing & queueing

| Recipe | What it shows | Runs as |
|---|---|---|
| [Forward an inbound SMS to other numbers](forward-an-inbound-sms-to-other-numbers/) | Send every text that arrives on your number on to a list of other numbers with the Messaging reply method, prefixed with the sender, without replying to the sender. | Python, TypeScript |
| [Run an SMS survey over several messages](run-an-sms-survey-over-several-messages/) | Text a customer a question, keep track of where each number is in the survey, ask the next question when a reply arrives, re-ask when it does not fit, and stop the moment they say STOP. | Python, TypeScript |
| [Send from a number group with sticky sender](send-from-a-number-group-with-sticky-sender/) | When you create a number group with sticky_sender: true, the platform picks From numbers out of that pool and holds one per recipient. A compat send names the group as MessagingServiceSid and carries no From. | Python |

### Tools & integrations

| Recipe | What it shows | Runs as |
|---|---|---|
| [Publish events to browsers with PubSub](publish-events-to-browsers-with-pubsub/) | A PubSub token grants read or write on named channels for a number of minutes. Your server mints one per member, and decides who may write. The browser never holds the project API token. | Python |
| [Text the caller during the call](text-the-caller-during-the-call/) | Have an AI agent tool text the caller during a live voice call without exposing the phone number to the model. | Python, Markup |

### Other

| Recipe | What it shows | Runs as |
|---|---|---|
| [Reply to an inbound SMS](reply-to-an-inbound-sms/) | Receive a text and answer it in the same thread. | Python, Markup |
| [Send an SMS](send-an-sms/) | Send an SMS with one REST call, and handle a request that fails. | Python |

## MFA

One-time codes over SMS or voice, verified by the platform.

### Other

| Recipe | What it shows | Runs as |
|---|---|---|
| [Send an OTP by SMS, with voice fallback](send-an-otp-by-sms-with-voice-fallback/) | The MFA API sends a code by SMS, re-sends it by voice call if asked, and verifies it; you store no codes. | Python |

## Video

Rooms, recording, streaming, and PSTN into a room.

### Call control

| Recipe | What it shows | Runs as |
|---|---|---|
| [Add a phone caller to a video room](add-a-phone-caller-to-a-video-room/) | Create a video room through REST, then connect a phone call to that room. | Markup, Python |
| [Create a video room and join from the browser](create-a-video-room-and-join-from-the-browser/) | A room is created over REST, a token is minted per participant, and the browser joins with layouts and screen share. | Python, TypeScript |
| [Launch a prebuilt video conference](launch-a-prebuilt-video-conference/) | Create a themed hosted video conference over REST, then retrieve participant tokens with names and access scopes. | Python |

### Monitoring

| Recipe | What it shows | Runs as |
|---|---|---|
| [Record a video room](record-a-video-room/) | Enable recording when you create a video room, then list or delete session recordings through the REST API. | Python |
| [Stream a video room to RTMP](stream-a-video-room-to-rtmp/) | Start, update, or stop a video room's RTMP stream through REST using your streaming server URL. | Python |

## Fax

Send and receive fax with status webhooks.

### Call control

| Recipe | What it shows | Runs as |
|---|---|---|
| [Receive an inbound fax](receive-an-inbound-fax/) | Receive an inbound fax at a webhook URL and get a status callback when delivery completes. | Markup, Python |
| [Send a fax](send-a-fax/) | A fax is sent from a document URL and its status webhook reports pages and result. | Python |

## Builds

A build is an application you deploy and operate, assembled from the recipes above.

### [AI Call Center](ai-call-center/)

Route callers with AI, queue by priority, connect browser-based human agents, and let supervisors listen, whisper, or barge in.

Composes: [Control which tools an AI agent can call at each step](scope-tools-per-step/), [Show the AI model only the fields it needs](hide-fields-from-the-model/), [Transfer a call without losing context](transfer-a-call-without-losing-context/), [Whisper a summary to the agent before connecting the caller](brief-the-human-before-the-bridge-completes/), [Hand off from AI to a human agent](hand-off-from-ai-to-a-human-agent/), [Listen to a live call](listen-to-a-live-call/), [Whisper to an agent mid-call](whisper-to-an-agent-mid-call/), [Offer a callback instead of a hold](offer-a-callback-instead-of-a-hold/), [Translate a call in real time](translate-a-call-in-real-time/), [Ground a voice AI agent in your documents](ground-an-agent-in-your-docs/)

### [Embed a state-aware voice agent in your web page](embed-a-state-aware-voice-agent-in-your-web-page/)

Embed a voice and video assistant that searches your documentation, knows the current page, and navigates visitors to relevant sections.

Composes: [Ground a voice AI agent in your documents](ground-an-agent-in-your-docs/), [Push events from a voice AI agent to the browser](push-events-from-an-agent-to-the-browser/), [Give a voice AI agent a video avatar](give-an-agent-a-video-avatar/), [Cover AI agent tool latency with fillers](cover-tool-latency-with-fillers/), [Let a browser dial your agent with no dashboard setup](let-a-browser-dial-your-agent-with-no-dashboard-setup/), [Call from a browser](call-from-a-browser/), [Inject a message into a live AI call](inject-a-message-into-a-live-ai-call/), [Configure a voice AI agent per request for many tenants](configure-an-agent-per-request/), [Keep per-call state server-side, keyed by call id](keep-heavy-state-out-of-global-data/), [Run a voice AI agent as an AWS Lambda function](run-an-agent-as-a-cloud-function/)
