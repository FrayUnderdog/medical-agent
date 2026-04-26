/**
 * Shared shell: theme (localStorage) + nav active state + mobile drawer.
 */
(function () {
  "use strict";

  var THEME_KEY = "medical_agent_mvp_theme";

  function getTheme() {
    var t = localStorage.getItem(THEME_KEY);
    return t === "dark" ? "dark" : "light";
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    if (theme === "dark") root.classList.add("theme-dark");
    else root.classList.remove("theme-dark");
    localStorage.setItem(THEME_KEY, theme);

    var btn = document.getElementById("themeToggle");
    if (btn) {
      btn.textContent = theme === "dark" ? "Light" : "Dark";
      btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      btn.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
    }
  }

  function toggleTheme() {
    applyTheme(getTheme() === "dark" ? "light" : "dark");
  }

  function normalizePath(pathname) {
    if (!pathname || pathname === "/") return "/";
    return pathname.replace(/\/+$/, "") || "/";
  }

  function setActiveNav() {
    var path = normalizePath(window.location.pathname);
    var links = document.querySelectorAll("[data-nav]");
    links.forEach(function (a) {
      var target = a.getAttribute("data-nav");
      if (!target) return;
      var t = normalizePath(target);
      var active = path === t || (t !== "/" && path.indexOf(t) === 0);
      a.classList.toggle("is-active", active);
    });
  }

  function wireMobileNav() {
    var toggle = document.getElementById("navMobileToggle");
    var drawer = document.getElementById("navDrawer");
    if (!toggle || !drawer) return;

    function close() {
      drawer.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    }

    function open() {
      drawer.classList.add("is-open");
      toggle.setAttribute("aria-expanded", "true");
    }

    toggle.addEventListener("click", function () {
      if (drawer.classList.contains("is-open")) close();
      else open();
    });

    drawer.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        close();
      });
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth >= 900) close();
    });
  }

  function init() {
    applyTheme(getTheme());
    setActiveNav();
    wireMobileNav();

    var themeBtn = document.getElementById("themeToggle");
    if (themeBtn) themeBtn.addEventListener("click", toggleTheme);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
