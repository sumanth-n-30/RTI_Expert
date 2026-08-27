// ── CHAT LOGIC ──

let CASE_CONTEXT = "";

let SYSTEM_PROMPT = `You are a helpful assistant assisting Indian citizens with their Right to Information (RTI) queries. You provide guidance on how to better structure applications under the RTI Act, 2005.

You have been provided with context about a specific RTI query. Use this to provide friendly, clear, and easy-to-understand advice. Avoid overly complex legal jargon.

Focus on being helpful. If the user asks how to change their query, provide a simpler version. If you mention rules like Section 8(1)(j), explain them simply (e.g., "rules regarding personal privacy").

Stay focused on RTI topics like drafting, timelines, and common reasons why requests might be sent back.

Keep responses concise and structured. Use bullet points or numbered lists when listing multiple points. Bold key terms. Format well for a chat UI.`;

let chatHistoryData = [];
let isLoading = false;

function loadChatContext() {
  const storedData = localStorage.getItem('active_rti');
  if (storedData && document.getElementById('side-doc-title')) {
    try {
      const data = JSON.parse(storedData);
      
      document.getElementById('side-doc-title').textContent = "Pasted Document";
      document.getElementById('side-doc-meta').textContent = new Date().toLocaleDateString();
      
      const isAccept = data.prediction && data.prediction.toLowerCase() === 'accepted';
      const badge = document.getElementById('side-pred-badge');
      if (badge) {
        badge.className = 'verdict-pill ' + (isAccept ? 'accept' : 'reject');
        // keep inline styles but update colors
        if(isAccept) {
           badge.style.background = 'rgba(22,163,74,0.15)';
           badge.style.color = '#4ade80';
        } else {
           badge.style.background = 'rgba(239,68,68,0.15)';
           badge.style.color = '#f87171';
        }
        badge.innerHTML = `<i class="ti ${isAccept ? 'ti-check' : 'ti-x'}" aria-hidden="true"></i> ${data.prediction || 'Unknown'}`;
      }
      
      const confText = document.getElementById('side-conf-text');
      if (confText) confText.textContent = (data.confidence || 0) + '% conf';
      
      const fill = document.getElementById('side-conf-fill');
      if (fill) {
        fill.style.width = (data.confidence || 0) + '%';
        fill.style.background = isAccept ? '#4ade80' : '#f87171';
      }
      
      const queryBox = document.getElementById('side-query-box');
      if (queryBox && data.query) {
        queryBox.textContent = data.query.length > 200 ? data.query.substring(0, 200) + '...' : data.query;
      }
      
      const insightsBox = document.getElementById('side-insights-box');
      if (insightsBox) {
        if (data.insights && data.insights.length > 0) {
          insightsBox.innerHTML = data.insights.map(i => `<div style="display:flex; align-items:flex-start; gap:8px; margin-bottom:8px; font-size:12.5px; color:var(--text-main); line-height:1.4;"><div style="width:6px; height:6px; background:#ef4444; border-radius:50%; flex-shrink:0; margin-top:6px;"></div>${i}</div>`).join('');
        } else {
          insightsBox.innerHTML = '<div style="color:var(--text-3); font-size:12.5px;">No major risks found</div>';
        }
      }
    } catch (e) {
      console.error("Failed to parse active RTI data:", e);
    }
  }

  // Update CASE_CONTEXT dynamically
  if (storedData) {
    try {
      const data = JSON.parse(storedData);
      CASE_CONTEXT = `
EXTRACTED RTI QUERY:
"${data.query || ''}"

ML PREDICTION: ${data.prediction || 'Unknown'} (${data.confidence || 0}% confidence)

IDENTIFIED REJECTION RISKS:
${data.insights && data.insights.length ? data.insights.join('\n') : 'None'}

AI-IMPROVED DRAFT (generated):
${data.draft || 'Not generated yet'}
`;
    } catch(e) {}
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Load dynamic context into the chat sidebar if it exists
  loadChatContext();

  // Session-based chat: clear old chats when browser reopens
  // sessionStorage survives page navigation but clears on browser close
  if (!sessionStorage.getItem('chatSessionActive')) {
    // New browser session — clear any stale chat history
    localStorage.removeItem('chatHistory');
    sessionStorage.setItem('chatSessionActive', 'true');
  }

  // Restore chat history only for current session
  const savedHistory = localStorage.getItem('chatHistory');
  if (savedHistory) {
    try {
      chatHistoryData = JSON.parse(savedHistory);
      if (chatHistoryData.length > 0) {
        const suggestions = document.getElementById('suggestions');
        if (suggestions) suggestions.style.display = 'none';
        
        chatHistoryData.forEach(msg => {
          if (msg.role === 'user') {
            appendMsg('user', msg.content.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'), msg.time || now());
          } else {
            appendMsg('assistant', formatResponse(msg.content), msg.time || now());
          }
        });
      }
    } catch (e) {
      console.error("Failed to restore chat history:", e);
    }
  }

  const ta = document.getElementById('chat-input');
  if(ta) {
    ta.focus();
  }
});

function clearChat() {
  chatHistoryData = [];
  localStorage.removeItem('chatHistory');
  const container = document.getElementById('messages');
  if (container) container.innerHTML = `
    <div class="empty-chat" id="empty-state">
      <i class="ti ti-messages" aria-hidden="true"></i>
      <h3>Chat about your RTI case</h3>
      <p>Ask about rejection risks, how to improve your draft, appeal options, or what similar cases decided.</p>
    </div>
  `;
  const suggestions = document.getElementById('suggestions');
  if (suggestions) suggestions.style.display = '';
}

function now() {
  return new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function sendSuggestion(btn) {
  const text = btn.textContent;
  document.getElementById('chat-input').value = text;
  sendMessage();
}

function appendMsg(role, html, time) {
  const empty = document.getElementById('empty-state');
  if (empty) empty.remove();

  const container = document.getElementById('messages');
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + (role === 'user' ? 'user' : 'assistant');

  const avatarDiv = document.createElement('div');
  avatarDiv.className = 'msg-avatar ' + (role === 'user' ? 'user-av' : 'ai');
  avatarDiv.innerHTML = role === 'user'
    ? '<i class="ti ti-user" aria-hidden="true"></i>'
    : '<i class="ti ti-robot" aria-hidden="true"></i>';

  const inner = document.createElement('div');
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = html;
  const timeEl = document.createElement('div');
  timeEl.className = 'msg-time';
  timeEl.textContent = time;
  inner.appendChild(bubble);
  inner.appendChild(timeEl);

  // Place assistant avatar on left, user context handles right
  wrap.appendChild(avatarDiv);
  wrap.appendChild(inner);
  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

function showTyping() {
  const empty = document.getElementById('empty-state');
  if (empty) empty.remove();

  const container = document.getElementById('messages');
  const wrap = document.createElement('div');
  wrap.className = 'msg assistant';
  wrap.id = 'typing-msg';

  const avatarDiv = document.createElement('div');
  avatarDiv.className = 'msg-avatar ai';
  avatarDiv.innerHTML = '<i class="ti ti-robot" aria-hidden="true"></i>';

  const bubble = document.createElement('div');
  bubble.className = 'bubble typing-indicator';
  bubble.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

  wrap.appendChild(avatarDiv);
  wrap.appendChild(bubble);
  container.appendChild(wrap);
  container.scrollTop = container.scrollHeight;
}

function removeTyping() {
  const el = document.getElementById('typing-msg');
  if (el) el.remove();
}

function formatResponse(text) {
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^### (.+)$/gm, '<strong style="font-size:13px;">$1</strong>')
    .replace(/^## (.+)$/gm, '<strong>$1</strong>')
    .replace(/^# (.+)$/gm, '<strong>$1</strong>');

  const lines = html.split('\n');
  let result = '';
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (/^[-*•]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      if (!inList) { result += '<ul>'; inList = true; }
      result += '<li>' + line.replace(/^[-*•]\s+/, '').replace(/^\d+\.\s+/, '') + '</li>';
    } else {
      if (inList) { result += '</ul>'; inList = false; }
      if (line) result += '<p>' + line + '</p>';
    }
  }
  if (inList) result += '</ul>';
  return result;
}

async function sendMessage() {
  if (isLoading) return;
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  input.style.height = 'auto';

  const suggestions = document.getElementById('suggestions');
  if(suggestions) suggestions.style.display = 'none';

  const t = now();
  appendMsg('user', text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'), t);

  chatHistoryData.push({ role: 'user', content: text, time: t });
  localStorage.setItem('chatHistory', JSON.stringify(chatHistoryData));

  isLoading = true;
  const sendBtn = document.getElementById('send-btn');
  if(sendBtn) sendBtn.disabled = true;
  showTyping();

  try {
    const resp = await fetch('http://127.0.0.1:5000/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    query: chatHistoryData[chatHistoryData.length - 1].content,
    context: typeof CASE_CONTEXT !== 'undefined' ? CASE_CONTEXT : ''
  })
});

    const data = await resp.json();
    removeTyping();

    if (!resp.ok) {
      appendMsg('assistant', `<div class="error-bubble">API error: ${data.error?.message || resp.status}</div>`, now());
    } else {
      let reply = "";
      
      // Defensive check for various response formats
      if (data && Array.isArray(data.content)) {
        reply = data.content.map(b => b.type === 'text' ? (b.text || "") : "").join("");
      } else if (data && typeof data.reply === 'string') {
        reply = data.reply;
      } else if (data && data.prediction) {
        // Fallback: If the server returns a prediction object but no 'reply' text
        reply = `I've analyzed your query and determined it is likely to be <strong>${data.prediction}</strong>.`;
      } else {
        reply = "Error: Received an invalid response format from the AI server.";
      }
      
      const replyTime = now();
      appendMsg('assistant', formatResponse(reply), replyTime);
      chatHistoryData.push({ role: 'assistant', content: reply, time: replyTime });
      localStorage.setItem('chatHistory', JSON.stringify(chatHistoryData));
    }
  } catch (err) {
    removeTyping();
    appendMsg('assistant', `<div class="error-bubble">Connection failed. Is the API running?</div>`, now());
  } finally {
    isLoading = false;
    if(sendBtn) sendBtn.disabled = false;
    input.focus();
  }
}

// ── OLD INDEX.HTML LOGIC (Preserved just in case) ──
const views = ['analyze','similar','history','tips'];
const topbarTitles = { analyze:'Analyze RTI Document', similar:'Similar Cases (RAG Search)', history:'My Analysis History', tips:'RTI Guidelines & Tips' };
const topbarBadges = { analyze:'Powered by ML + RAG', similar:'Semantic similarity search', history:'12 analyses this month', tips:'RTI Act 2005' };

function switchView(v) {
  views.forEach(id => {
    const el = document.getElementById('view-'+id);
    if(el) el.classList.toggle('active', id===v);
  });
  document.querySelectorAll('.nav-item').forEach((el,i) => {
    if(el.getAttribute('onclick')) {
      el.classList.toggle('active', el.getAttribute('onclick').includes("'"+v+"'"));
    }
  });
  const tTitle = document.getElementById('topbar-title');
  if(tTitle) tTitle.textContent = topbarTitles[v];
  const tBadge = document.getElementById('topbar-badge');
  if(tBadge) tBadge.textContent = topbarBadges[v];
}

const tabs = ['upload','paste','results'];
function switchTab(t) {
  tabs.forEach(id => {
    const el = document.getElementById('tab-'+id);
    if(el) el.style.display = (id===t) ? 'block' : 'none';
  });
  document.querySelectorAll('.tab').forEach((el,i) => {
    if(el.getAttribute('onclick')) {
      el.classList.toggle('active', el.getAttribute('onclick').includes("'"+t+"'"));
    }
  });
}

function goResults() { switchTab('results'); }

document.addEventListener('DOMContentLoaded', () => {
  const ta = document.getElementById('rti-input');
  const cc = document.getElementById('char-count');
  if(ta && cc) ta.addEventListener('input', () => cc.textContent = ta.value.length + ' characters');
});
