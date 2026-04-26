/**
 * Consultation page: POST /chat + client-side session summary (localStorage only).
 * Extraction rules live in mergeUserTextIntoState() and deriveRiskLevel().
 */
(function () {
  "use strict";

  var SESSION_KEY = "medical_agent_mvp_session_id";
  var SUMMARY_PREFIX = "medical_agent_mvp_summary_";

  function getSessionId() {
    var v = localStorage.getItem(SESSION_KEY);
    return v && v.length ? v : null;
  }

  function summaryStorageKey() {
    return SUMMARY_PREFIX + (getSessionId() || "pending");
  }

  function defaultSummaryState() {
    return {
      name: null,
      age: null,
      primary: null,
      symptoms: [],
      duration: null,
      bodyLoc: null,
      department: null,
      allergies: [],
      conditions: [],
      risk: "unknown",
    };
  }

  var summaryState = defaultSummaryState();

  var WORD_NUM = {
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
    six: 6,
    seven: 7,
    eight: 8,
    nine: 9,
    ten: 10,
    eleven: 11,
    twelve: 12,
  };

  var NAME_STOP = new Set([
    "here",
    "not",
    "fine",
    "good",
    "sick",
    "able",
    "having",
    "still",
    "very",
    "okay",
    "ok",
    "sorry",
    "worried",
    "experiencing",
    "feeling",
    "doing",
    "seeing",
    "trying",
  ]);

  function normalizeSpace(s) {
    return (s || "").replace(/\s+/g, " ").trim();
  }

  function uniqCi(list) {
    var out = [];
    var seen = new Set();
    (list || []).forEach(function (x) {
      var t = normalizeSpace(String(x));
      if (!t) return;
      var k = t.toLowerCase();
      if (seen.has(k)) return;
      seen.add(k);
      out.push(t);
    });
    return out;
  }

  function mergeStates(base, patch) {
    var out = {
      name: patch.name != null && patch.name !== "" ? patch.name : base.name,
      age: patch.age != null && patch.age !== "" ? patch.age : base.age,
      primary: patch.primary != null && patch.primary !== "" ? patch.primary : base.primary,
      symptoms: uniqCi((base.symptoms || []).concat(patch.symptoms || [])),
      duration: patch.duration != null && patch.duration !== "" ? patch.duration : base.duration,
      bodyLoc: patch.bodyLoc != null && patch.bodyLoc !== "" ? patch.bodyLoc : base.bodyLoc,
      department: patch.department != null && patch.department !== "" ? patch.department : base.department,
      allergies: uniqCi((base.allergies || []).concat(patch.allergies || [])),
      conditions: uniqCi((base.conditions || []).concat(patch.conditions || [])),
      risk: patch.risk || base.risk,
    };
    return out;
  }

  function parseWordOrDigitQuantity(m) {
    if (!m) return null;
    var w = m.toLowerCase();
    if (/^\d+$/.test(w)) return parseInt(w, 10);
    if (w === "a" || w === "an") return 1;
    return WORD_NUM[w] != null ? WORD_NUM[w] : null;
  }

  function parseDurationPhrase(t) {
    var s = t;
    if (/\bsince\s+yesterday\b/i.test(s)) return "Since yesterday";
    if (/\bsince\s+last\s+week\b/i.test(s)) return "Since last week";
    if (/\bsince\s+monday\b/i.test(s)) return "Since Monday";

    var m = s.match(
      /\bfor\s+((?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d{1,2}))\s+(hour|hours|day|days|week|weeks|month|months)\b/i
    );
    if (m) {
      var n = parseWordOrDigitQuantity(m[1]);
      var unit = m[2].toLowerCase();
      if (n != null) return "For " + n + " " + unit;
    }

    m = s.match(/\bfor\s+the\s+past\s+(\d{1,2})\s+(day|days|week|weeks)\b/i);
    if (m) return "For the past " + m[1] + " " + m[2];

    m = s.match(/\b(\d{1,2})\s*(?:-|–)?\s*(day|days|week|weeks)\b/i);
    if (m && /\bfor\b/i.test(s)) return "For " + m[1] + " " + m[2];

    return null;
  }

  function extractAge(t) {
    var m = t.match(/\b(\d{1,3})\s*years?\s*old\b/i);
    if (m) return m[1];
    m = t.match(/\bage\s*[:is]?\s*(\d{1,3})\b/i);
    if (m) return m[1];
    m = t.match(/\bi\s*'?m\s+(\d{1,3})(?:\s*years?\s*old)?\b/i);
    if (m) return m[1];
    m = t.match(/\bi\s+am\s+(\d{1,3})(?:\s*years?\s*old)?\b/i);
    if (m) return m[1];
    return null;
  }

  function extractName(t) {
    var m = t.match(/\bmy\s+name\s+is\s+([A-Za-z][A-Za-z'-]{0,39})\b/i);
    if (m) return normalizeSpace(m[1].replace(/['"]+$/g, ""));
    m = t.match(/\b(?:call\s+me|i'?m\s+called)\s+([A-Za-z][A-Za-z'-]{0,39})\b/i);
    if (m) return normalizeSpace(m[1].replace(/['"]+$/g, ""));
    m = t.match(/\bi\s+am\s+([A-Za-z][a-z]{1,29})\b/i);
    if (m) {
      var w = m[1];
      if (NAME_STOP.has(w.toLowerCase())) return null;
      if (/^\d+$/.test(w)) return null;
      return w.charAt(0).toUpperCase() + w.slice(1);
    }
    return null;
  }

  function extractSymptomsFromText(t) {
    var low = t.toLowerCase();
    var found = [];
    var add = function (label, ok) {
      if (ok) found.push(label);
    };

    add("Fever", /\bfever\b/.test(low));
    add("Headache", /\b(headache|migraine)\b/.test(low));
    add("Cough", /\bcough(ing)?\b/.test(low));
    add("Skin rash", /\b(rash|hives)\b/.test(low));
    add("Chest pain", /\bchest\s*pain\b/.test(low));
    add(
      "Shortness of breath",
      /\b(shortness\s+of\s+breath|difficulty\s+breathing|trouble\s+breathing|can'?t\s+breathe|cannot\s+breathe)\b/.test(low)
    );
    add("Nausea", /\bnausea\b|\bnauseous\b/.test(low));
    add("Vomiting", /\bvomit(ing)?\b|\bthrew\s+up\b/.test(low));
    add("Diarrhea", /\bdiarrhea\b|\bloose\s+stool\b/.test(low));
    add("Dizziness", /\bdizz(y|iness)\b|\blightheaded\b/.test(low));
    add("Sore throat", /\bsore\s+throat\b/.test(low));
    add("Abdominal pain", /\b(stomach|abdominal|belly)\s+pain\b/.test(low));
    add("Fatigue", /\b(fatigue|tired|exhausted)\b/.test(low));
    return found;
  }

  function extractAllergies(t) {
    var out = [];
    var m = t.match(/\ballergic\s+to\s+([A-Za-z0-9][A-Za-z0-9\s\-]{1,48})\b/i);
    if (m) out.push(normalizeSpace(m[1].replace(/[.,;]+$/, "")));
    m = t.match(/\ballergy\s*:\s*([^\n.]{2,48})/i);
    if (m) out.push(normalizeSpace(m[1].replace(/[.,;]+$/, "")));
    m = t.match(/\ballergy\s+to\s+([A-Za-z0-9][A-Za-z0-9\s\-]{1,48})\b/i);
    if (m) out.push(normalizeSpace(m[1].replace(/[.,;]+$/, "")));
    m = t.match(/\ballergies\s+include\s+([^\n.]{2,48})/i);
    if (m) out.push(normalizeSpace(m[1].replace(/[.,;]+$/, "")));
    return out;
  }

  function extractConditions(t) {
    var low = t.toLowerCase();
    var out = [];
    if (/\bdiabetes\b|\bdiabetic\b/.test(low)) out.push("Diabetes");
    if (/\bhypertension\b|\bhigh\s+blood\s+pressure\b/.test(low)) out.push("Hypertension");
    if (/\basthma\b/.test(low)) out.push("Asthma");
    return out;
  }

  function hasEmergencySignals(t) {
    var low = t.toLowerCase();
    return (
      /\bchest\s+pain\b/.test(low) ||
      /\bstroke\b/.test(low) ||
      /\bsevere\s+bleeding\b/.test(low) ||
      /\bhemoptysis\b|\bcoughing\s+up\s+blood\b|\bblood\s+in\s+sputum\b/.test(low) ||
      /\b(shortness\s+of\s+breath|difficulty\s+breathing|trouble\s+breathing|can'?t\s+breathe|cannot\s+breathe)\b/.test(low)
    );
  }

  function deriveRiskLevel(state, fullText) {
    if (hasEmergencySignals(fullText)) return "emergency";
    var syms = state.symptoms || [];
    var emergencySymptom = syms.some(function (s) {
      return s === "Chest pain" || s === "Shortness of breath";
    });
    if (emergencySymptom) return "emergency";

    var hasAcute = syms.length > 0;
    if (hasAcute) return "monitor";

    var hasStructured =
      (state.age != null && state.age !== "") ||
      (state.duration != null && state.duration !== "") ||
      (state.allergies && state.allergies.length) ||
      (state.conditions && state.conditions.length) ||
      (state.name != null && state.name !== "");
    if (hasStructured) return "routine";

    return "unknown";
  }

  /**
   * Lightweight rule-based extraction from a single user utterance.
   * Merges into existing summaryState (accumulates list fields).
   */
  function mergeUserTextIntoState(prev, text) {
    var raw = normalizeSpace(text);
    if (!raw) return prev;

    var patch = {
      name: extractName(raw),
      age: extractAge(raw),
      symptoms: extractSymptomsFromText(raw),
      duration: parseDurationPhrase(raw),
      allergies: extractAllergies(raw),
      conditions: extractConditions(raw),
    };

    var merged = mergeStates(prev, patch);
    merged.risk = deriveRiskLevel(merged, raw);
    return merged;
  }

  function persistSummary() {
    try {
      localStorage.setItem(summaryStorageKey(), JSON.stringify(summaryState));
    } catch (e) {
      /* ignore quota */
    }
  }

  function loadSummaryFromStorage() {
    try {
      var raw = localStorage.getItem(summaryStorageKey());
      if (!raw) {
        summaryState = defaultSummaryState();
        return;
      }
      var o = JSON.parse(raw);
      if (!o || typeof o !== "object") {
        summaryState = defaultSummaryState();
        return;
      }
      summaryState = mergeStates(defaultSummaryState(), {
        name: o.name,
        age: o.age,
        primary: o.primary,
        symptoms: o.symptoms,
        duration: o.duration,
        bodyLoc: o.bodyLoc,
        department: o.department,
        allergies: o.allergies,
        conditions: o.conditions,
        risk: o.risk,
      });
      var hint = [summaryState.symptoms || [], summaryState.allergies || [], summaryState.conditions || []]
        .flat()
        .join(" ")
        .toLowerCase();
      summaryState.risk = deriveRiskLevel(summaryState, hint);
    } catch (e) {
      summaryState = defaultSummaryState();
    }
  }

  function flushPendingToSession(sessionId) {
    if (!sessionId) return;
    try {
      localStorage.setItem(SUMMARY_PREFIX + sessionId, JSON.stringify(summaryState));
      localStorage.removeItem(SUMMARY_PREFIX + "pending");
    } catch (e) {
      /* ignore */
    }
  }

  function applyUserText(text) {
    summaryState = mergeUserTextIntoState(summaryState, text);
    persistSummary();
    renderSummary();
  }

  function renderSummary() {
    function setText(id, val, fallback) {
      var n = document.getElementById(id);
      if (!n) return;
      var v = val != null && String(val).trim() !== "" ? String(val).trim() : fallback;
      n.textContent = v;
    }

    setText("sumName", summaryState.name, "Not provided");
    setText("sumAge", summaryState.age, "Not provided");
    setText("sumPrimary", summaryState.primary, "Not provided");

    var sym = summaryState.symptoms && summaryState.symptoms.length ? summaryState.symptoms.join(", ") : null;
    setText("sumSymptoms", sym, "Not provided");

    setText("sumDuration", summaryState.duration, "Not provided");
    setText("sumBodyLoc", summaryState.bodyLoc, "Not provided");

    var alg = summaryState.allergies && summaryState.allergies.length ? summaryState.allergies.join(", ") : null;
    setText("sumAllergies", alg, "Not provided");

    var cond = summaryState.conditions && summaryState.conditions.length ? summaryState.conditions.join(", ") : null;
    setText("sumConditions", cond, "Not provided");

    setText("sumDept", summaryState.department, "Not provided");

    var riskEl = document.getElementById("sumRisk");
    if (!riskEl) return;
    var r = (summaryState.risk || "unknown").toLowerCase();
    if (r === "self_care") r = "routine";
    if (r !== "unknown" && r !== "routine" && r !== "monitor" && r !== "emergency" && r !== "urgent") r = "unknown";

    riskEl.textContent = r.charAt(0).toUpperCase() + r.slice(1);
    riskEl.setAttribute("data-risk", r);
    riskEl.className = "risk-badge risk-badge--" + r;
  }

  function applyPatientSummaryFromServer(ps) {
    if (!ps || typeof ps !== "object") return;
    var bodyLoc =
      ps.body_location_label ||
      [ps.side_or_location, ps.body_part].filter(Boolean).join(" ").trim() ||
      null;
    summaryState = {
      name: ps.name || null,
      age: ps.age || null,
      primary: ps.chief_complaint || null,
      symptoms: Array.isArray(ps.symptoms) ? ps.symptoms : [],
      duration: ps.duration || null,
      bodyLoc: bodyLoc,
      department: ps.likely_department || null,
      allergies: Array.isArray(ps.allergies) ? ps.allergies : [],
      conditions: Array.isArray(ps.chronic_conditions) ? ps.chronic_conditions : [],
      risk: (ps.risk_level || "unknown").toLowerCase(),
    };
    persistSummary();
    renderSummary();
  }

  function updateDevTrace(data) {
    var pre = document.getElementById("devTraceBody");
    if (!pre) return;
    var kr = (data.tool_outputs && data.tool_outputs.knowledge_rag) || {};
    var payload = {
      tool_trace: data.tool_trace || [],
      retrieval_trace: kr.retrieval_trace || null,
      sources: kr.sources || [],
      patient_intake: data.tool_outputs && data.tool_outputs.patient_intake,
      guardrails: data.tool_outputs && data.tool_outputs.guardrails,
      triage: data.tool_outputs && data.tool_outputs.triage_suggestion,
    };
    pre.textContent = JSON.stringify(payload, null, 2);
  }

  function updateSessionIdDisplay(id) {
    var el = document.getElementById("sessionIdDisplay");
    if (el) {
      el.textContent = id || "— (assigned on first send)";
      el.title = id || "";
    }
  }

  function setSessionId(id) {
    var prev = getSessionId();
    if (id) {
      localStorage.setItem(SESSION_KEY, id);
      if (!prev) flushPendingToSession(id);
    } else {
      localStorage.removeItem(SESSION_KEY);
    }
    updateSessionIdDisplay(id);
  }

  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text != null) n.textContent = text;
    return n;
  }

  var messagesEl = document.getElementById("messages");
  var inputEl = document.getElementById("messageInput");
  var sendBtn = document.getElementById("sendBtn");

  function getWelcomeEl() {
    return document.getElementById("welcomeEmpty");
  }

  function scrollBottom() {
    if (!messagesEl) return;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideWelcome() {
    var w = getWelcomeEl();
    if (w) w.classList.add("hidden");
  }

  function showWelcome() {
    var w = getWelcomeEl();
    if (w) w.classList.remove("hidden");
  }

  function ensureWelcomeRow() {
    if (!messagesEl) return;
    if (getWelcomeEl()) return;
    var w = document.createElement("div");
    w.id = "welcomeEmpty";
    w.className = "muted";
    w.style.padding = "8px 4px 16px";
    w.style.fontSize = "0.875rem";
    w.style.lineHeight = "1.6";
    w.innerHTML =
      "Chat with the assistant. Describe symptoms or tap a quick prompt. Press <strong>Enter</strong> to send, <strong>Shift+Enter</strong> for a new line.";
    messagesEl.insertBefore(w, messagesEl.firstChild);
  }

  function appendUser(text) {
    if (!messagesEl) return;
    hideWelcome();
    var row = el("div", "msg msg--user");
    var bubble = el("div", "msg__bubble", text);
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    scrollBottom();
  }

  function appendAssistant(data) {
    if (!messagesEl) return;
    hideWelcome();
    var row = el("div", "msg msg--assistant");
    var wrap = el("div", "");
    var bubble = el("div", "msg__bubble", data.reply || "");
    wrap.appendChild(bubble);
    row.appendChild(wrap);
    messagesEl.appendChild(row);
    scrollBottom();
  }

  function appendError(msg) {
    if (!messagesEl) return;
    hideWelcome();
    var row = el("div", "msg msg--assistant");
    row.appendChild(el("div", "error-bubble", msg));
    messagesEl.appendChild(row);
    scrollBottom();
  }

  function setLoading(on) {
    if (!sendBtn || !inputEl) return;
    sendBtn.disabled = on;
    inputEl.disabled = on;
    var existing = document.getElementById("typingRow");
    if (on) {
      if (existing) return;
      var row = el("div", "msg msg--assistant");
      row.id = "typingRow";
      var pill = el("div", "typing-indicator");
      pill.appendChild(el("span", "typing-indicator__dot"));
      pill.appendChild(el("span", "typing-indicator__dot"));
      pill.appendChild(el("span", "typing-indicator__dot"));
      var label = document.createElement("span");
      label.textContent = "Assistant is responding…";
      pill.appendChild(label);
      row.appendChild(pill);
      messagesEl.appendChild(row);
    } else if (existing) {
      existing.remove();
    }
    scrollBottom();
  }

  async function sendMessage() {
    if (!messagesEl || !inputEl || !sendBtn) return;
    var text = (inputEl.value || "").trim();
    if (!text) return;

    applyUserText(text);
    appendUser(text);
    inputEl.value = "";
    setLoading(true);

    try {
      var res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: getSessionId(),
          message: text,
        }),
      });
      var raw = await res.text();
      if (!res.ok) throw new Error(res.status + " " + raw.slice(0, 240));
      var data = JSON.parse(raw);
      setSessionId(data.session_id);
      applyPatientSummaryFromServer(data.patient_summary);
      updateDevTrace(data);
      appendAssistant(data);
    } catch (e) {
      appendError(
        "Could not reach /chat. Start the API (e.g. uvicorn main:app) or check the console. " +
          (e && e.message ? e.message : String(e))
      );
    } finally {
      setLoading(false);
      inputEl.focus();
    }
  }

  function wire() {
    if (!messagesEl || !inputEl || !sendBtn) return;

    loadSummaryFromStorage();
    renderSummary();
    updateSessionIdDisplay(getSessionId());

    sendBtn.addEventListener("click", sendMessage);
    inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    document.querySelectorAll("[data-chip]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var t = btn.getAttribute("data-chip") || "";
        inputEl.value = t;
        applyUserText(t);
        inputEl.focus();
      });
    });

    var newSessionBtn = document.getElementById("newSessionBtn");
    if (newSessionBtn) {
      newSessionBtn.addEventListener("click", function () {
        var sid = getSessionId();
        if (sid) {
          try {
            localStorage.removeItem(SUMMARY_PREFIX + sid);
          } catch (e) {
            /* ignore */
          }
        }
        try {
          localStorage.removeItem(SUMMARY_PREFIX + "pending");
        } catch (e) {
          /* ignore */
        }
        localStorage.removeItem(SESSION_KEY);
        summaryState = defaultSummaryState();
        renderSummary();
        updateSessionIdDisplay(null);
        if (messagesEl) {
          messagesEl.innerHTML = "";
          ensureWelcomeRow();
        }
        showWelcome();
      });
    }

    inputEl.focus();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
