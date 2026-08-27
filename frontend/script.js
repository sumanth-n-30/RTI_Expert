// ── CHAT LOGIC ──

const CASE_CONTEXT = `
CASE DOCUMENT: MGNREGS_RTI_2024.pdf

EXTRACTED RTI QUERY:
"I request information regarding the list of beneficiaries enrolled under the MGNREGS scheme in Gram Panchayat Kotagiri, Nilgiris district, Tamil Nadu, for financial year 2023–24. Specifically: (a) Names and job card numbers of all registered beneficiaries, (b) Number of days worked per beneficiary, (c) Wages paid, mode of payment, and any pending dues."

ML PREDICTION: Accepted (78% confidence)
REJECTION RISK SCORE: 22%

IDENTIFIED REJECTION RISKS:
1. Request for individual names alongside financial data may trigger Section 8(1)(j) exemption (personal information).
2. Broad scope — "all registered beneficiaries" without a count cap risks a voluminous-request rejection.
3. Jurisdiction must be the district MGNREGS office PIO, not the state level.

EXTRACTED TAGS: Public record, Government scheme, Contains personal names (risk)

SIMILAR CASES RETRIEVED (12 total, avg 67% accepted):
- RTI/TN/2023/04872: MGNREGS wage records, Coimbatore — Partially accepted; aggregate data given, names exempted under 8(1)(j). 96% match.
- RTI/TN/2022/09134: Job card names, Tirunelveli — Rejected (personal info). Revised aggregate query succeeded. 88% match.
- RTI/KA/2023/11290: Pending dues, ward-wise GP — Fully accepted in 15 days. 81% match.
- RTI/MH/2023/06671: All MGNREGS records, Nashik — Voluminous rejection; appeal with narrowed scope succeeded. 74% match.

AI-IMPROVED DRAFT (generated):
Removed individual names and job card numbers; replaced with ward-wise aggregate beneficiary count. Changed "number of days per beneficiary" to category-wise aggregate. Added ward-total for pending dues. Addressed to District Programme Coordinator, MGNREGS, Nilgiris.
`;

const SYSTEM_PROMPT = `You are a helpful assistant assisting Indian citizens with their Right to Information (RTI) queries. You provide guidance on how to better structure applications under the RTI Act, 2005.

You have been provided with context about a specific RTI query. Use this to provide friendly, clear, and easy-to-understand advice. Avoid overly complex legal jargon.

Focus on being helpful. If the user asks how to change their query, provide a simpler version. If you mention rules like Section 8(1)(j), explain them simply (e.g., "rules regarding personal privacy").

Stay focused on RTI topics like drafting, timelines, and common reasons why requests might be sent back.

Keep responses concise and structured. Use bullet points or numbered lists when listing multiple points. Bold key terms. Format well for a chat UI.

CASE CONTEXT:
${CASE_CONTEXT}`;

let history = [];
let isLoading = false;

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

  history.push({ role: 'user', content: text });

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
    query: history[history.length - 1].content
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

      history.push({ role: 'assistant', content: reply });
      appendMsg('assistant', formatResponse(reply), now());
    }
  } catch (err) {
    removeTyping();
    appendMsg('assistant', `<div class="error-bubble">Network error: ${err.message}</div>`, now());
  }

  isLoading = false;
  if(sendBtn) sendBtn.disabled = false;
  document.getElementById('chat-input').focus();
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
