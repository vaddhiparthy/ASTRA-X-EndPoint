# ASTRA‑X‑Aggregator

ASTRA‑X‑Aggregator is a modular home‑assistant backend and chat interface designed to glue
together arbitrary inputs (webhooks, REST APIs and user chat) with a locally hosted
language model.  It exposes a simple HTTP API and a persistent chat UI so that
messages coming from different sources are merged into a single conversation.

The project is intentionally broken down into reusable components:

* **Backend** – Powered by FastAPI, it provides endpoints for chat, webhooks,
  history retrieval and data browsing.  Messages are persisted in a SQLite
  database with two tables: a **short‑term log** used to build context for
  inference, and a **medium‑term store** intended for nightly summarisation (not
  implemented yet).  The server calls a running [Ollama](https://docs.ollama.com/)
  instance to generate replies and supports arbitrary system prompts via an
  environment variable.
* **Frontend** – A single page HTML/JS application with two tabs: a WhatsApp‑like
  dark chat interface and a simple data browser.  The interface polls the backend
  for new messages, displays connection status and allows users to query the
  database by date range.  It borrows the dark glassy theme from the ASTRA‑X
  dashboard without altering the existing design.
* **Database** – SQLite is used via SQLAlchemy to store messages and summaries.
  Each message record stores a timestamp, role (user/assistant/event), source,
  channel, text and optional raw payload.  Summaries are kept in a separate
  table for future use.

## Features

* Accepts messages from multiple sources via `/chat` and `/webhook/…` endpoints.
* Normalises incoming payloads to plain text and writes them to the short‑term log.
* Augments each request with recent context (last 15 minutes) and up to 30
  summaries from the medium‑term store before calling the Ollama model.
* Stores every input and LLM response in the database with timestamps and
  metadata.
* Provides a persistent chat interface that loads history from the database rather
  than relying on local storage.  Opening the UI on any device shows the same
  conversation.
* Includes a data browser allowing the user to filter log entries by date/time.

## Prerequisites

* **Ollama** – The backend delegates inference to a locally running Ollama
  service.  See the [official documentation](https://docs.ollama.com/) for
  installation instructions.  The default API endpoint is
  `http://localhost:11434`.  When the backend runs inside Docker you may need
  to set `OLLAMA_HOST=http://host.docker.internal:11434` or
  `OLLAMA_HOST=http://172.17.0.1:11434` depending on your platform.
* **Docker** – To build and run the container image.  Alternatively you can run
  the app directly with `uvicorn` after installing dependencies from
  `requirements.txt`.

## Running locally

1. **Install dependencies**

   ```bash
   cd ASTRA-X-Aggregator
   pip install -r requirements.txt
   ```

2. **Start the server** – Set at least the model name and (optionally)
   a system prompt.  The example below uses `localhost` to reach a host
   Ollama instance.

   ```bash
   export OLLAMA_HOST=http://localhost:11434
   export OLLAMA_MODEL=YOUR_MODEL_NAME
   export SYSTEM_PROMPT="You are a helpful home assistant."
   python -m app.main
   ```

3. **Open the UI** – Navigate to `http://127.0.0.1:8000` in your browser.  You
   should see the chat tab.  Send a message and observe the assistant’s reply.

## Building and running with Docker

This repository includes a `Dockerfile` that packages the backend and
frontend.  To build and run the container, execute the following commands
from the root of the project:

```bash
# Build the image
docker build -t astra-x-aggregator .

# Run the container (replace OLLAMA_MODEL with your installed model)
docker run -p 8000:8000 --name astra-x-aggregator \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=YOUR_MODEL_NAME \
  -e SYSTEM_PROMPT="You are a helpful home assistant." \
  astra-x-aggregator
```

On Linux without Docker Desktop you might need to adjust the value of
`OLLAMA_HOST` or run with `--network=host` so that the container can
reach your Ollama service.  Once running, open `http://localhost:8000` in
your browser.

## REST API

| Endpoint               | Method | Description                                          |
|------------------------|--------|------------------------------------------------------|
| `/`                    | GET    | Serves the single‑page chat and browser UI.          |
| `/chat`                | POST   | Accepts user chat messages.  Returns the assistant’s response. |
| `/webhook/uptime-kuma` | POST   | Receives Uptime Kuma webhook payloads and triggers a summary. |
| `/webhook/generic`     | POST   | Accepts arbitrary JSON payloads and produces a summary. |
| `/history`             | GET    | Fetches chat log entries.  Accepts an optional `after` (ISO timestamp) query parameter to return only newer messages. |
| `/data`                | GET    | Retrieves log entries between two datetimes.  Requires `start` and `end` query parameters (ISO 8601). |
| `/health`              | GET    | Returns a simple JSON status indicating whether the backend is running. |

## Future work

* **Nightly summarisation** – A background job could summarise the last 24 hours of
  messages and append the result to the medium‑term store.  Those summaries
  would be used instead of raw messages for longer context windows.
* **Authentication** – Protect the UI and API endpoints with a login.
* **Streaming responses** – Use server‑sent events or WebSockets to display
  partial model output as it is generated.

## License

This project is provided under the MIT licence.  See the `LICENSE` file
for details.