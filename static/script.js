// Client-side logic for ASTRA‑X‑Aggregator

document.addEventListener('DOMContentLoaded', () => {
  // Tabs and panes
  const chatTab = document.getElementById('chatTab');
  const dataTab = document.getElementById('dataTab');
  const chatPane = document.getElementById('chatPane');
  const dataPane = document.getElementById('dataPane');

  // Status indicator and message area
  const statusEl = document.getElementById('chatStatus');
  const messagesDiv = document.getElementById('messages');
  let lastTs = null;

  /**
   * Switch between the Chat and Data panes.
   * @param {boolean} toChat True to show the chat pane, false for data browser
   */
  function switchTab(toChat) {
    if (toChat) {
      chatTab.classList.add('active');
      dataTab.classList.remove('active');
      chatPane.classList.add('active');
      dataPane.classList.remove('active');
    } else {
      dataTab.classList.add('active');
      chatTab.classList.remove('active');
      dataPane.classList.add('active');
      chatPane.classList.remove('active');
    }
  }

  chatTab.addEventListener('click', () => switchTab(true));
  dataTab.addEventListener('click', () => switchTab(false));

  /**
   * Append a chat bubble to the message pane.
   * @param {string} content Text of the message
   * @param {string} role One of 'user', 'assistant' or 'system'
   */
  function appendMessage(content, role) {
    const msg = document.createElement('div');
    msg.classList.add('message');
    // normalise unknown roles to system
    if (role !== 'user' && role !== 'assistant') {
      role = 'system';
    }
    msg.classList.add(role);
    msg.textContent = content;
    messagesDiv.appendChild(msg);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  }

  /**
   * Fetch new messages from the server.  If `initial` is true the
   * endpoint is called without a query parameter and up to 50 messages are
   * returned.  Otherwise only messages newer than `lastTs` are requested.
   * After appending new messages the `lastTs` is updated.
   * @param {boolean} initial Whether this is the first call
   */
  async function fetchHistory(initial = false) {
    let url = '/history';
    if (!initial && lastTs) {
      url += '?after=' + encodeURIComponent(lastTs);
    }
    try {
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      data.forEach((msg) => {
        appendMessage(msg.text, msg.role);
        lastTs = msg.ts;
      });
    } catch (err) {
      console.error(err);
    }
  }

  /**
   * Check backend health and update the status indicator.  The indicator
   * text and colour reflect whether the API appears reachable.  This
   * function does not poll the Ollama host itself – it simply verifies
   * that the FastAPI server is running.
   */
  async function updateStatus() {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        statusEl.textContent = 'Connected';
        statusEl.style.color = 'var(--ok)';
      } else {
        statusEl.textContent = 'Disconnected';
        statusEl.style.color = 'var(--danger)';
      }
    } catch (err) {
      statusEl.textContent = 'Disconnected';
      statusEl.style.color = 'var(--danger)';
    }
  }

  // Initial load
  fetchHistory(true);
  updateStatus();

  // Poll for new messages every 5 seconds
  setInterval(() => {
    fetchHistory(false);
  }, 5000);
  // Poll for status every 30 seconds
  setInterval(() => {
    updateStatus();
  }, 30000);

  /**
   * Handle chat form submission.  Posts the user’s message to the server
   * and immediately appends it.  After receiving the assistant reply,
   * the history fetcher will pick it up in the next poll.  Errors are
   * appended as system messages.
   * @param {Event} event Form submission event
   */
  async function sendChat(event) {
    event.preventDefault();
    const input = document.getElementById('messageInput');
    const text = input.value.trim();
    if (!text) return;
    appendMessage(text, 'user');
    input.value = '';
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) {
        const errData = await res.json();
        appendMessage('Error: ' + (errData.detail || res.statusText), 'system');
      } else {
        const data = await res.json();
        // Append assistant reply immediately rather than waiting for poll
        appendMessage(data.reply, 'assistant');
        // Update lastTs to force subsequent polls to only load newer messages
        lastTs = new Date().toISOString();
      }
    } catch (err) {
      appendMessage('Error: ' + err, 'system');
    }
  }

  const messageForm = document.getElementById('messageForm');
  messageForm.addEventListener('submit', sendChat);

  /**
   * Handle data query form.  Sends a GET request to the `/data` endpoint
   * with ISO‑8601 start and end times and populates the table with
   * the resulting messages.
   * @param {Event} event Form submission event
   */
  async function queryData(event) {
    event.preventDefault();
    const startVal = document.getElementById('startTime').value;
    const endVal = document.getElementById('endTime').value;
    if (!startVal || !endVal) return;
    // Convert local datetime strings to ISO 8601 in UTC by constructing a
    // Date object.  `datetime-local` values do not include timezone info.
    const startIso = new Date(startVal).toISOString();
    const endIso = new Date(endVal).toISOString();
    const url = `/data?start=${encodeURIComponent(startIso)}&end=${encodeURIComponent(endIso)}`;
    try {
      const res = await fetch(url);
      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || res.statusText);
        return;
      }
      const data = await res.json();
      const tbody = document.querySelector('#dataTable tbody');
      tbody.innerHTML = '';
      data.forEach((msg) => {
        const tr = document.createElement('tr');
        const date = new Date(msg.ts);
        const timeCell = document.createElement('td');
        timeCell.textContent = date.toLocaleString();
        const roleCell = document.createElement('td');
        roleCell.textContent = msg.role;
        const sourceCell = document.createElement('td');
        sourceCell.textContent = msg.source;
        const textCell = document.createElement('td');
        textCell.textContent = msg.text;
        tr.appendChild(timeCell);
        tr.appendChild(roleCell);
        tr.appendChild(sourceCell);
        tr.appendChild(textCell);
        tbody.appendChild(tr);
      });
    } catch (err) {
      alert('Error: ' + err);
    }
  }

  const queryForm = document.getElementById('queryForm');
  queryForm.addEventListener('submit', queryData);
});