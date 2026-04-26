/**
 * Medical Agent MVP — demo UI (vanilla JS).
 * POST /chat, session in localStorage, light/dark theme.
 */
(function () {
  "use strict";

  var THEME_KEY = "medical_agent_mvp_theme";
  var SESSION_KEY = "medical_agent_mvp_session_id";

  var els = {
    clock: document.getElementById("clock"),
    themeBtn: document.getElementById("themeBtn"),
    clearBtn: document.getElementById("clearBtn"),
    newChatBtn: document.getElementById("newChatBtn"),
    sessionIdEl: document.getElementById("sessionIdDisplay"),
    chatScroll: document.getElementById("chatScroll"),
    emergencyStrip: document.getElementById("emergencyStrip"),
    welcomeCard: document.getElementById("welcomeCard"),
    messages: document.getElementById("messages"),
    input: document.getElementById("messageInput"),
    sendBtn: document.getElementById("sendBtn"),
    exampleBtns: document.querySelectorAll("[data-example]"),
    // Views + nav
    viewLabel: document.getElementById("viewLabel"),
    viewHome: document.getElementById("viewHome"),
    viewChat: document.getElementById("viewChat"),
    viewEmergency: document.getElementById("viewEmergency"),
    viewTriage: document.getElementById("viewTriage"),
    viewDept: document.getElementById("viewDept"),
    viewSummary: document.getElementById("viewSummary"),
    devPanel: document.getElementById("devPanel"),
    navHome: document.getElementById("navHome"),
    navChat: document.getElementById("navChat"),
    navTriage: document.getElementById("navTriage"),
    navDept: document.getElementById("navDept"),
    navSummary: document.getElementById("navSummary"),
    devToggleBtn: document.getElementById("devToggleBtn"),
    devCloseBtn: document.getElementById("devCloseBtn"),
    // View widgets
    intakeForm: document.getElementById("intakeForm"),
    intakeAge: document.getElementById("intakeAge"),
    intakeSex: document.getElementById("intakeSex"),
    intakeSymptoms: document.getElementById("intakeSymptoms"),
    startConsultBtn: document.getElementById("startConsultBtn"),
    goChatBtn: document.getElementById("goChatBtn"),
    emergencyText: document.getElementById("emergencyText"),
    mockCallBtn: document.getElementById("mockCallBtn"),
    backToChatBtn: document.getElementById("backToChatBtn"),
    triageCard: document.getElementById("triageCard"),
    triageToDeptBtn: document.getElementById("triageToDeptBtn"),
    triageToSummaryBtn: document.getElementById("triageToSummaryBtn"),
    triageToChatBtn: document.getElementById("triageToChatBtn"),
    deptCard: document.getElementById("deptCard"),
    deptToSummaryBtn: document.getElementById("deptToSummaryBtn"),
    deptToChatBtn: document.getElementById("deptToChatBtn"),
    summaryCard: document.getElementById("summaryCard"),
    clinicalNote: document.getElementById("clinicalNote"),
    debugSummary: document.getElementById("debugSummary"),
    debugTrace: document.getElementById("debugTrace"),
    debugOutputs: document.getElementById("debugOutputs"),
  };

  var appState = {
    view: "home",
    intake: { age: "", sex: "", symptoms: "" },
    lastUserMessage: null,
    lastResponse: null,
    transcript: [],
  };

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function tickClock() {
    if (!els.clock) return;
    var d = new Date();
    els.clock.textContent =
      pad(d.getHours()) +
      ":" +
      pad(d.getMinutes()) +
      ":" +
      pad(d.getSeconds());
  }

  function getTheme() {
    var t = localStorage.getItem(THEME_KEY);
    return t === "dark" ? "dark" : "light";
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    localStorage.setItem(THEME_KEY, theme);
    if (els.themeBtn) {
      els.themeBtn.textContent = theme === "dark" ? "Light Mode" : "Dark Mode";
      els.themeBtn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    }
  }

  function toggleTheme() {
    applyTheme(getTheme() === "dark" ? "light" : "dark");
  }

  function getSessionId() {
    var v = localStorage.getItem(SESSION_KEY);
    return v && v.length ? v : null;
  }

  function setSessionId(id) {
    if (id) localStorage.setItem(SESSION_KEY, id);
    else localStorage.removeItem(SESSION_KEY);
    updateSessionDisplay();
  }

  function updateSessionDisplay() {
    var id = getSessionId();
    if (els.sessionIdEl) {
      els.sessionIdEl.textContent = id || "— (new on next send)";
      els.sessionIdEl.title = id || "";
    }
  }

  function scrollChatToBottom() {
    if (els.chatScroll) els.chatScroll.scrollTop = els.chatScroll.scrollHeight;
  }

  function hideWelcome() {
    if (els.welcomeCard) els.welcomeCard.classList.add("hidden");
  }

  function showWelcome() {
    if (els.welcomeCard) els.welcomeCard.classList.remove("hidden");
  }

  function clearMessages() {
    if (els.messages) els.messages.innerHTML = "";
    if (els.emergencyStrip) els.emergencyStrip.classList.add("hidden");
    showWelcome();
    appState.lastUserMessage = null;
    appState.lastResponse = null;
    appState.transcript = [];
    renderAllViews();
  }

  function clearSession() {
    setSessionId(null);
    clearMessages();
  }

  function isEmergencyResponse(data) {
    return data.triage_level === "emergency" || data.guardrail_triggered === true;
  }

  function setNavActive(id) {
    [els.navHome, els.navChat, els.navTriage, els.navDept, els.navSummary].forEach(function (b) {
      if (!b) return;
      if (b.id === id) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
  }

  function setView(view) {
    appState.view = view;
    if (els.viewLabel) {
      var label =
        view === "home"
          ? "Home"
          : view === "chat"
            ? "Consultation"
            : view === "triage"
              ? "Triage"
              : view === "dept"
                ? "Department"
                : view === "summary"
                  ? "Summary"
                  : "Emergency";
      els.viewLabel.textContent = label;
    }
    if (els.viewHome) els.viewHome.classList.toggle("hidden", view !== "home");
    if (els.viewChat) els.viewChat.classList.toggle("hidden", view !== "chat");
    if (els.viewTriage) els.viewTriage.classList.toggle("hidden", view !== "triage");
    if (els.viewDept) els.viewDept.classList.toggle("hidden", view !== "dept");
    if (els.viewSummary) els.viewSummary.classList.toggle("hidden", view !== "summary");
    if (els.viewEmergency) els.viewEmergency.classList.toggle("hidden", view !== "emergency");

    setNavActive(
      view === "home"
        ? "navHome"
        : view === "chat"
          ? "navChat"
          : view === "triage"
            ? "navTriage"
            : view === "dept"
              ? "navDept"
              : "navSummary"
    );
  }

  function toggleDevPanel(visible) {
    if (!els.devPanel) return;
    var show = visible != null ? !!visible : els.devPanel.classList.contains("hidden");
    if (show) els.devPanel.classList.remove("hidden");
    else els.devPanel.classList.add("hidden");
  }

  function setEmergencyStrip(visible) {
    if (!els.emergencyStrip) return;
    if (visible) els.emergencyStrip.classList.remove("hidden");
    else els.emergencyStrip.classList.add("hidden");
  }

  function triageBadgeClass(level) {
    if (!level)
      return "border-slate-200 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200";
    switch (level) {
      case "emergency":
        return "border-red-300 bg-red-50 text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-100";
      case "urgent":
        return "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-600 dark:bg-amber-950 dark:text-amber-100";
      case "self_care":
        return "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-100";
      case "routine":
        return "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-700 dark:bg-sky-950 dark:text-sky-100";
      default:
        return "border-blue-300 bg-blue-50 text-blue-900 dark:border-blue-700 dark:bg-blue-950 dark:text-blue-100";
    }
  }

  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text != null) n.textContent = text;
    return n;
  }

  function appendUserBubble(text) {
    hideWelcome();
    var wrap = el("div", "flex justify-end mb-4");
    var inner = el("div", "max-w-[85%] md:max-w-[75%]");
    var bubble = el(
      "div",
      "rounded-2xl rounded-br-md bg-teal-600 px-4 py-3 text-sm text-white shadow-md shadow-teal-600/20 whitespace-pre-wrap break-words",
      text
    );
    inner.appendChild(bubble);
    wrap.appendChild(inner);
    els.messages.appendChild(wrap);
    scrollChatToBottom();
  }

  function renderSymptomChips(container, toolOutputs) {
    var se = toolOutputs && toolOutputs.symptom_extraction;
    var symptoms = se && se.symptoms;
    if (!symptoms || !symptoms.length) return;
    var row = el("div", "flex flex-wrap gap-2 mt-3");
    row.appendChild(el("span", "text-xs font-medium text-slate-500 dark:text-slate-400", "Symptoms"));
    symptoms.forEach(function (s) {
      var chip = el(
        "span",
        "inline-flex items-center rounded-full border border-teal-200 bg-teal-50 px-2.5 py-0.5 text-xs font-medium text-teal-800 dark:border-teal-800 dark:bg-teal-950 dark:text-teal-100",
        s.replace(/_/g, " ")
      );
      row.appendChild(chip);
    });
    container.appendChild(row);
  }

  function appendAssistantCard(data) {
    hideWelcome();
    var emergency = isEmergencyResponse(data);

    var wrap = el("div", "flex justify-start mb-4");
    var inner = el("div", "max-w-[92%] md:max-w-[80%] w-full");

    var cardClass =
      "rounded-2xl rounded-bl-md border bg-white p-4 shadow-sm dark:bg-slate-900/80 " +
      (emergency
        ? "border-red-400 ring-2 ring-red-200 dark:border-red-600 dark:ring-red-900/60"
        : "border-slate-200 dark:border-slate-700");

    var card = el("div", cardClass);

    if (emergency) {
      var alertBox = el(
        "div",
        "emergency-strip mb-3 rounded-lg border-2 border-red-500 bg-red-50 p-3 text-sm font-semibold text-red-900 dark:bg-red-950 dark:text-red-50"
      );
      alertBox.appendChild(
        document.createTextNode(
          "Potential emergency detected. Please call local emergency services or go to the nearest ER."
        )
      );
      card.appendChild(alertBox);
    }

    var reply = el(
      "div",
      "text-sm leading-relaxed text-slate-800 dark:text-slate-100 whitespace-pre-wrap break-words",
      data.reply || ""
    );
    card.appendChild(reply);

    renderSymptomChips(card, data.tool_outputs);

    var meta = el("div", "mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-700");

    var triage = data.triage_level;
    var triageLabel = el(
      "span",
      "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold " + triageBadgeClass(triage),
      triage ? "triage: " + triage : "triage: —"
    );
    meta.appendChild(triageLabel);

    var gr = el(
      "span",
      "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium " +
        (data.guardrail_triggered
          ? "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-700 dark:bg-rose-950 dark:text-rose-100"
          : "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"),
      "guardrail: " + (data.guardrail_triggered ? "triggered" : "clear")
    );
    meta.appendChild(gr);

    var sid = el(
      "span",
      "inline-flex max-w-full truncate rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-600 dark:bg-slate-800 dark:text-slate-300",
      "session: " + (data.session_id || "")
    );
    sid.title = data.session_id || "";
    meta.appendChild(sid);

    card.appendChild(meta);

    var det = document.createElement("details");
    det.className = "mt-3 rounded-lg border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-950/50";
    var sum = document.createElement("summary");
    sum.className =
      "cursor-pointer select-none px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800";
    sum.textContent = "tool_outputs (JSON)";
    var pre = el(
      "pre",
      "max-h-56 overflow-auto border-t border-slate-200 p-3 text-[11px] leading-relaxed text-slate-700 dark:border-slate-700 dark:text-slate-300"
    );
    pre.textContent = JSON.stringify(data.tool_outputs || {}, null, 2);
    det.appendChild(sum);
    det.appendChild(pre);
    card.appendChild(det);

    inner.appendChild(card);
    wrap.appendChild(inner);
    els.messages.appendChild(wrap);

    setEmergencyStrip(emergency);
    scrollChatToBottom();
  }

  function computeDepartment(triageLevel, guardrailTriggered) {
    if (guardrailTriggered || triageLevel === "emergency") {
      return {
        title: "Emergency Department (ER)",
        detail:
          "This looks like a potential emergency. In a real product, we would recommend immediate evaluation in the ER or calling emergency services.",
        tagClass: "border-red-300 bg-red-50 text-red-900 dark:border-red-700 dark:bg-red-950 dark:text-red-50",
      };
    }
    if (triageLevel === "urgent") {
      return {
        title: "Urgent Care / Same-day Clinic",
        detail:
          "This may need prompt evaluation today. In a real workflow we’d route to urgent care, a same-day clinic slot, or telehealth escalation.",
        tagClass:
          "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-600 dark:bg-amber-950 dark:text-amber-100",
      };
    }
    if (triageLevel === "routine") {
      return {
        title: "Primary Care / Routine visit",
        detail:
          "This appears non-urgent. A routine primary care visit (or self-care with monitoring) is reasonable depending on risk factors.",
        tagClass:
          "border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-700 dark:bg-sky-950 dark:text-sky-100",
      };
    }
    return {
      title: "Self-care + watchful waiting",
      detail:
        "This appears low acuity. Provide supportive care, monitor symptoms, and seek care if worsening or new red flags appear.",
      tagClass:
        "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-100",
    };
  }

  function buildClinicalNote(userMessage, data) {
    var tool = (data && data.tool_outputs) || {};
    var se = tool.symptom_extraction || {};
    var tri = tool.triage_suggestion || {};
    var rag = tool.knowledge_rag || {};
    var gr = tool.guardrails || {};

    var lines = [];
    lines.push("CLINICAL HANDOFF NOTE (DEMO)");
    lines.push("—");
    lines.push("Chief complaint:");
    lines.push("- " + (userMessage || "—"));
    lines.push("");
    lines.push("Structured extraction:");
    lines.push("- symptoms: " + JSON.stringify(se.symptoms || []));
    lines.push("- duration_days: " + (se.duration_days == null ? "null" : String(se.duration_days)));
    lines.push("");
    lines.push("Safety policy / guardrails:");
    lines.push("- triggered: " + String(!!data.guardrail_triggered));
    lines.push("- severity: " + (gr.severity || "null"));
    lines.push("- matched_rule_ids: " + JSON.stringify(gr.matched_rule_ids || []));
    lines.push("- matched_phrases: " + JSON.stringify(gr.matched_phrases || []));
    lines.push("- reason: " + (gr.reason || "—"));
    lines.push("");
    lines.push("Triage:");
    lines.push("- triage_level: " + (data.triage_level || tri.triage_level || "—"));
    lines.push("");
    lines.push("Retrieval:");
    lines.push("- retrieval_provider: " + (data.retrieval_provider || "—"));
    lines.push("- sources: " + JSON.stringify(rag.sources || []));
    if (rag.reranker_used != null) {
      lines.push("- reranker_used: " + String(!!rag.reranker_used));
      lines.push("- recall_top_k: " + String(rag.recall_top_k || 0) + ", rerank_top_n: " + String(rag.rerank_top_n || 0));
    }
    lines.push("");
    lines.push("Retrieved context (truncated):");
    var ctx = (rag.retrieved_context || "").trim();
    lines.push(ctx ? ctx.slice(0, 800) + (ctx.length > 800 ? "…" : "") : "—");
    lines.push("");
    lines.push("Tool trace:");
    lines.push(JSON.stringify(data.tool_trace || [], null, 2));
    return lines.join("\n");
  }

  function renderDebug(data) {
    if (!els.debugSummary || !els.debugTrace || !els.debugOutputs) return;
    if (!data) {
      els.debugSummary.textContent = "Send a message to see debug metadata.";
      els.debugTrace.textContent = "";
      els.debugOutputs.textContent = "";
      return;
    }
    var rag = (data.tool_outputs && data.tool_outputs.knowledge_rag) || {};
    var sources = rag.sources || [];
    var provider = data.retrieval_provider || rag.retrieval_provider || "—";
    var triage = data.triage_level || "—";
    var rerank = rag.reranker_used != null ? String(!!rag.reranker_used) : "—";

    els.debugSummary.innerHTML = "";
    els.debugSummary.appendChild(el("div", "text-sm font-semibold text-slate-800 dark:text-slate-100", "Latest response"));
    var ul = el("ul", "mt-2 list-inside list-disc text-sm text-slate-700 dark:text-slate-200");
    ul.appendChild(el("li", "", "triage_level: " + triage));
    ul.appendChild(el("li", "", "retrieval_provider: " + provider));
    ul.appendChild(el("li", "", "reranker_used: " + rerank));
    ul.appendChild(el("li", "", "retrieved_sources: " + (sources.length ? sources.join(", ") : "—")));
    els.debugSummary.appendChild(ul);

    els.debugTrace.textContent = JSON.stringify(data.tool_trace || [], null, 2);
    els.debugOutputs.textContent = JSON.stringify(data.tool_outputs || {}, null, 2);
  }

  function renderDepartment(data) {
    if (!els.deptCard) return;
    if (!data) {
      els.deptCard.textContent = "Send a message first to generate a recommendation.";
      return;
    }
    var rec = computeDepartment(data.triage_level, data.guardrail_triggered);
    els.deptCard.innerHTML = "";
    var tag = el("div", "inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold " + rec.tagClass, rec.title);
    els.deptCard.appendChild(tag);
    els.deptCard.appendChild(el("p", "mt-3 text-sm text-slate-700 dark:text-slate-200", rec.detail));
  }

  function renderTriage(data) {
    if (!els.triageCard) return;
    if (!data) {
      els.triageCard.textContent = "Send a message first to generate a triage result.";
      return;
    }
    var tool = data.tool_outputs || {};
    var se = tool.symptom_extraction || {};
    var symptoms = se.symptoms || [];
    var duration = se.duration_days;
    var triage = data.triage_level || "—";
    var emergency = isEmergencyResponse(data);

    var next =
      triage === "urgent"
        ? "Recommended next step: get same-day evaluation (urgent care / clinician)."
        : triage === "routine"
          ? "Recommended next step: routine visit or monitor with supportive care."
          : triage === "self_care"
            ? "Recommended next step: self-care + monitor; seek care if worsening."
            : "Recommended next step: emergency evaluation now.";

    els.triageCard.innerHTML = "";
    var badge = el(
      "div",
      "inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold " + triageBadgeClass(triage),
      emergency ? "EMERGENCY" : String(triage).toUpperCase().replace(/_/g, " ")
    );
    els.triageCard.appendChild(badge);
    els.triageCard.appendChild(
      el(
        "p",
        "mt-3 text-sm text-slate-700 dark:text-slate-200",
        "Symptoms: " + (symptoms.length ? symptoms.join(", ").replace(/_/g, " ") : "—")
      )
    );
    els.triageCard.appendChild(
      el(
        "p",
        "mt-1 text-sm text-slate-700 dark:text-slate-200",
        "Duration: " + (duration == null ? "—" : String(duration) + " day(s)")
      )
    );
    els.triageCard.appendChild(el("p", "mt-3 text-sm font-semibold text-slate-900 dark:text-white", next));
  }

  function renderSummary(data) {
    if (!els.summaryCard) return;
    if (!data) {
      els.summaryCard.textContent = "Send a message first to generate a summary.";
      return;
    }
    var tool = data.tool_outputs || {};
    var se = tool.symptom_extraction || {};
    var symptoms = se.symptoms || [];
    var duration = se.duration_days;
    var triage = data.triage_level || "—";
    var dept = computeDepartment(data.triage_level, data.guardrail_triggered).title;

    els.summaryCard.innerHTML = "";
    els.summaryCard.appendChild(el("div", "text-sm font-semibold text-slate-900 dark:text-white", "Patient summary"));
    var ul = el("ul", "mt-2 list-inside list-disc text-sm text-slate-700 dark:text-slate-200");
    ul.appendChild(el("li", "", "symptoms: " + (symptoms.length ? symptoms.join(", ").replace(/_/g, " ") : "—")));
    ul.appendChild(el("li", "", "duration_days: " + (duration == null ? "—" : String(duration))));
    ul.appendChild(el("li", "", "triage_level: " + String(triage)));
    ul.appendChild(el("li", "", "next_step: " + dept));
    els.summaryCard.appendChild(ul);
  }

  function renderEmergency(data) {
    if (!els.emergencyText) return;
    var msg = (data && data.reply) || "Potential emergency detected. Please seek emergency care now.";
    els.emergencyText.textContent = msg;
  }

  function renderClinical(data) {
    if (!els.clinicalNote) return;
    if (!data) {
      els.clinicalNote.textContent = "Send a message first to generate a clinical note.";
      return;
    }
    els.clinicalNote.textContent = buildClinicalNote(appState.lastUserMessage, data);
  }

  function renderAllViews() {
    var d = appState.lastResponse;
    renderDebug(d);
    renderDepartment(d);
    renderTriage(d);
    renderSummary(d);
    renderEmergency(d);
    renderClinical(d);
  }

  function appendErrorBubble(message) {
    hideWelcome();
    var wrap = el("div", "flex justify-start mb-4");
    var card = el(
      "div",
      "max-w-[92%] rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-100",
      message
    );
    wrap.appendChild(card);
    els.messages.appendChild(wrap);
    scrollChatToBottom();
  }

  function setLoading(loading) {
    els.sendBtn.disabled = loading;
    els.input.disabled = loading;
    if (loading) {
      var typing = document.getElementById("typingRow");
      if (!typing) {
        typing = el("div", "flex justify-start mb-2");
        typing.id = "typingRow";
        var pill = el(
          "div",
          "inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500 shadow-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
        );
        pill.appendChild(el("span", "h-2 w-2 animate-pulse rounded-full bg-teal-500"));
        pill.appendChild(document.createTextNode("Assistant is typing…"));
        typing.appendChild(pill);
        els.messages.appendChild(typing);
      }
      typing.classList.remove("hidden");
    } else {
      var t = document.getElementById("typingRow");
      if (t) t.remove();
    }
    scrollChatToBottom();
  }

  async function sendMessage() {
    var text = (els.input.value || "").trim();
    if (!text) return;

    appendUserBubble(text);
    els.input.value = "";
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
      if (!res.ok) {
        throw new Error(res.status + " " + raw.slice(0, 200));
      }
      var data = JSON.parse(raw);
      setSessionId(data.session_id);
      updateSessionDisplay();
      appendAssistantCard(data);
      appState.lastUserMessage = text;
      appState.lastResponse = data;
      appState.transcript.push({ role: "user", content: text });
      appState.transcript.push({ role: "assistant", content: data.reply || "" });
      renderAllViews();
      if (isEmergencyResponse(data)) {
        setView("emergency");
      } else {
        setView("triage");
      }
    } catch (e) {
      appendErrorBubble("Something went wrong. " + (e && e.message ? e.message : String(e)));
    } finally {
      setLoading(false);
      els.input.focus();
    }
  }

  function wire() {
    if (els.themeBtn) els.themeBtn.addEventListener("click", toggleTheme);
    if (els.clearBtn) els.clearBtn.addEventListener("click", clearSession);
    if (els.newChatBtn) els.newChatBtn.addEventListener("click", clearSession);
    if (els.sendBtn) els.sendBtn.addEventListener("click", sendMessage);
    if (els.navHome) els.navHome.addEventListener("click", function () { setView("home"); });
    if (els.navChat) els.navChat.addEventListener("click", function () { setView("chat"); });
    if (els.navTriage) els.navTriage.addEventListener("click", function () { setView("triage"); });
    if (els.navDept) els.navDept.addEventListener("click", function () { setView("dept"); });
    if (els.navSummary) els.navSummary.addEventListener("click", function () { setView("summary"); });
    if (els.devToggleBtn) els.devToggleBtn.addEventListener("click", function () { toggleDevPanel(); });
    if (els.devCloseBtn) els.devCloseBtn.addEventListener("click", function () { toggleDevPanel(false); });

    if (els.backToChatBtn) els.backToChatBtn.addEventListener("click", function () { setView("chat"); });
    if (els.mockCallBtn) {
      els.mockCallBtn.addEventListener("click", function () {
        alert("Demo only: In a real product this would initiate an emergency call workflow.");
      });
    }
    if (els.triageToDeptBtn) els.triageToDeptBtn.addEventListener("click", function () { setView("dept"); });
    if (els.triageToSummaryBtn) els.triageToSummaryBtn.addEventListener("click", function () { setView("summary"); });
    if (els.triageToChatBtn) els.triageToChatBtn.addEventListener("click", function () { setView("chat"); });
    if (els.deptToSummaryBtn) els.deptToSummaryBtn.addEventListener("click", function () { setView("summary"); });
    if (els.deptToChatBtn) els.deptToChatBtn.addEventListener("click", function () { setView("chat"); });

    if (els.goChatBtn) els.goChatBtn.addEventListener("click", function () { setView("chat"); });
    if (els.intakeForm) {
      els.intakeForm.addEventListener("submit", function (e) {
        e.preventDefault();
        var age = (els.intakeAge && els.intakeAge.value ? els.intakeAge.value : "").trim();
        var sex = els.intakeSex && els.intakeSex.value ? els.intakeSex.value : "";
        var sym = (els.intakeSymptoms && els.intakeSymptoms.value ? els.intakeSymptoms.value : "").trim();
        appState.intake = { age: age, sex: sex, symptoms: sym };
        if (sym) {
          els.input.value =
            (age ? "Age: " + age + ". " : "") +
            (sex ? "Sex: " + sex + ". " : "") +
            sym;
        }
        setView("chat");
        if (els.input) els.input.focus();
      });
    }

    if (els.input) {
      els.input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });
    }

    els.exampleBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var t = btn.getAttribute("data-example") || "";
        els.input.value = t;
        els.input.focus();
      });
    });
  }

  function init() {
    applyTheme(getTheme());
    tickClock();
    setInterval(tickClock, 1000);
    updateSessionDisplay();
    wire();
    setView("home");
    renderAllViews();
    if (els.input) els.input.focus();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
