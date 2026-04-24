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
  }

  function clearSession() {
    setSessionId(null);
    clearMessages();
  }

  function isEmergencyResponse(data) {
    return data.triage_level === "emergency" || data.guardrail_triggered === true;
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
    if (els.input) els.input.focus();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
