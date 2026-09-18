/* eLearning front-end behaviour. ES module, no inline handlers, CSP-safe.
   Every feature is opt-in through data attributes so pages stay declarative. */

const THEME_KEY = "elearning.theme";

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

/* ---- theme -------------------------------------------------------------- */
function applyTheme(pref) {
  const root = document.documentElement;
  let dark = pref === "dark";
  if (pref === "system") {
    dark = !window.matchMedia("(prefers-color-scheme: light)").matches;
  }
  root.setAttribute("data-theme", dark ? "dark" : "light");
  root.setAttribute("data-theme-pref", pref);
  document.querySelectorAll("[data-theme-set]").forEach((el) => {
    el.setAttribute("aria-checked", el.dataset.themeSet === pref ? "true" : "false");
  });
}

function initTheme() {
  const pref = document.documentElement.getAttribute("data-theme-pref") || "dark";
  applyTheme(pref);
  document.querySelectorAll("[data-theme-set]").forEach((el) => {
    el.addEventListener("click", (event) => {
      event.preventDefault();
      const value = el.dataset.themeSet;
      try { localStorage.setItem(THEME_KEY, value); } catch (e) { /* ignore */ }
      applyTheme(value);
    });
  });
  const media = window.matchMedia("(prefers-color-scheme: light)");
  media.addEventListener("change", () => {
    if ((document.documentElement.getAttribute("data-theme-pref") || "system") === "system") applyTheme("system");
  });
}

/* ---- mobile navigation -------------------------------------------------- */
function initMobileNav() {
  const toggle = document.querySelector("[data-nav-toggle]");
  const panel = document.querySelector("[data-mobile-nav]");
  if (!toggle || !panel) return;
  toggle.addEventListener("click", () => {
    const open = panel.classList.toggle("open");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
}

/* ---- search overlay ----------------------------------------------------- */
function initSearch() {
  const overlay = document.querySelector("[data-search-overlay]");
  if (!overlay) return;
  const input = overlay.querySelector("input[type=search]");
  const results = overlay.querySelector("[data-search-results]");
  const endpoint = overlay.dataset.searchEndpoint;
  const labels = JSON.parse(overlay.dataset.labels || "{}");
  let lastFocus = null;
  let timer = null;
  let controller = null;

  const open = () => {
    lastFocus = document.activeElement;
    overlay.classList.add("open");
    overlay.removeAttribute("hidden");
    input.focus();
    document.body.classList.add("overflow-hidden");
  };
  const close = () => {
    overlay.classList.remove("open");
    overlay.setAttribute("hidden", "");
    document.body.classList.remove("overflow-hidden");
    if (lastFocus) lastFocus.focus();
  };
  document.querySelectorAll("[data-search-open]").forEach((el) => el.addEventListener("click", (e) => { e.preventDefault(); open(); }));
  overlay.querySelectorAll("[data-search-close]").forEach((el) => el.addEventListener("click", close));
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && overlay.classList.contains("open")) close();
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); }
  });

  const render = (data) => {
    results.replaceChildren();
    const groups = [
      ["courses", labels.courses || "Courses", (c) => [c.title, c.short_description, c.url]],
      ["lessons", labels.lessons || "Lessons", (l) => [l.title, l.course, l.url]],
      ["resources", labels.resources || "Resources", (r) => [r.title, "", r.url]],
    ];
    let total = 0;
    groups.forEach(([key, label, map]) => {
      const items = data[key] || [];
      if (!items.length) return;
      total += items.length;
      const head = document.createElement("div");
      head.className = "group";
      head.textContent = label;
      results.appendChild(head);
      items.forEach((item) => {
        const [title, sub, url] = map(item);
        const a = document.createElement("a");
        a.href = url;
        a.textContent = title;
        if (sub) { const s = document.createElement("small"); s.textContent = sub; a.appendChild(s); }
        results.appendChild(a);
      });
    });
    if (!total) {
      const empty = document.createElement("div");
      empty.className = "state";
      empty.textContent = labels.empty || "No results";
      results.appendChild(empty);
    }
  };

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { results.replaceChildren(); return; }
    timer = setTimeout(async () => {
      if (controller) controller.abort();
      controller = new AbortController();
      const loading = document.createElement("div");
      loading.className = "state";
      loading.textContent = labels.loading || "Searching…";
      results.replaceChildren(loading);
      try {
        const response = await fetch(`${endpoint}?q=${encodeURIComponent(q)}`, { credentials: "same-origin", signal: controller.signal });
        if (!response.ok) throw new Error("search failed");
        render(await response.json());
      } catch (err) {
        if (err.name === "AbortError") return;
        const fail = document.createElement("div");
        fail.className = "state";
        fail.textContent = labels.error || "Search is unavailable";
        results.replaceChildren(fail);
      }
    }, 220);
  });
}

/* ---- lesson sidebar + heartbeat ----------------------------------------- */
function initLesson() {
  const toggle = document.querySelector("[data-sidebar-toggle]");
  const sidebar = document.querySelector("[data-lesson-sidebar]");
  if (toggle && sidebar) {
    toggle.addEventListener("click", () => {
      const open = sidebar.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
  const page = document.querySelector("[data-lesson-heartbeat]");
  if (!page) return;
  const url = page.dataset.lessonHeartbeat;
  let seconds = 0;
  let visible = !document.hidden;
  document.addEventListener("visibilitychange", () => { visible = !document.hidden; });
  setInterval(() => { if (visible) seconds += 15; }, 15000);
  setInterval(() => {
    if (seconds <= 0) return;
    const payload = seconds;
    seconds = 0;
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ seconds: payload }),
      keepalive: true,
    }).catch(() => {});
  }, 60000);
}

/* ---- confirm dialogs ---------------------------------------------------- */
function initConfirm() {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });
}

/* ---- tabs (query-string based, progressive) ----------------------------- */
function initTabs() {
  document.querySelectorAll("[data-tabs]").forEach((nav) => {
    const tabs = Array.from(nav.querySelectorAll("[data-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-tab-panel]"));
    const activate = (name) => {
      tabs.forEach((t) => t.setAttribute("aria-selected", t.dataset.tab === name ? "true" : "false"));
      panels.forEach((p) => { if (p.dataset.tabPanel === name) p.removeAttribute("hidden"); else p.setAttribute("hidden", ""); });
    };
    tabs.forEach((t) => t.addEventListener("click", (e) => {
      e.preventDefault();
      activate(t.dataset.tab);
      history.replaceState(null, "", `?tab=${t.dataset.tab}`);
    }));
  });
}

/* ---- sortable lists (drag & drop; buttons remain for keyboard users) ---- */
function initSortable() {
  document.querySelectorAll("[data-sortable]").forEach((list) => {
    const url = list.dataset.reorderUrl;
    let dragged = null;
    list.querySelectorAll("li[draggable=true]").forEach((item) => {
      item.addEventListener("dragstart", () => { dragged = item; item.classList.add("dragging"); });
      item.addEventListener("dragend", () => { item.classList.remove("dragging"); list.querySelectorAll(".drop-target").forEach((el) => el.classList.remove("drop-target")); });
      item.addEventListener("dragover", (e) => { e.preventDefault(); item.classList.add("drop-target"); });
      item.addEventListener("dragleave", () => item.classList.remove("drop-target"));
      item.addEventListener("drop", async (e) => {
        e.preventDefault();
        if (!dragged || dragged === item) return;
        const items = Array.from(list.children);
        if (items.indexOf(dragged) < items.indexOf(item)) item.after(dragged); else item.before(dragged);
        const ids = Array.from(list.children).map((li) => Number(li.dataset.id));
        try {
          const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
            body: JSON.stringify({ order: ids }),
          });
          if (!response.ok) throw new Error();
          list.querySelectorAll("[data-order-label]").forEach((el, i) => { el.textContent = String(i + 1); });
        } catch (err) {
          window.location.reload();
        }
      });
    });
  });
}

/* ---- quiz timer --------------------------------------------------------- */
function initQuizTimer() {
  const timer = document.querySelector("[data-quiz-deadline]");
  if (!timer) return;
  const deadline = new Date(timer.dataset.quizDeadline).getTime();
  const form = document.querySelector("[data-quiz-form]");
  const tick = () => {
    const left = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
    const m = String(Math.floor(left / 60)).padStart(2, "0");
    const s = String(left % 60).padStart(2, "0");
    timer.textContent = `${m}:${s}`;
    if (left <= 60) timer.classList.add("low");
    if (left <= 0 && form && !form.dataset.submitted) {
      form.dataset.submitted = "1";
      form.requestSubmit();
    }
  };
  tick();
  setInterval(tick, 1000);
}

/* ---- notifications badge refresh --------------------------------------- */
function initNotifications() {
  const badge = document.querySelector("[data-unread-badge]");
  if (!badge || !badge.dataset.endpoint) return;
  setInterval(async () => {
    try {
      const response = await fetch(badge.dataset.endpoint, { credentials: "same-origin" });
      if (!response.ok) return;
      const data = await response.json();
      badge.textContent = data.unread > 0 ? String(data.unread) : "";
      badge.hidden = data.unread === 0;
    } catch (e) { /* offline */ }
  }, 90000);
}

/* ---- question editor (option rows per question type) -------------------- */
function initQuestionEditor() {
  const editor = document.querySelector("[data-question-editor]");
  if (!editor) return;
  const select = editor.querySelector("select[name=question_type]");
  const apply = () => {
    const type = select.value;
    editor.querySelectorAll("[data-qtype-only]").forEach((el) => {
      const allowed = el.dataset.qtypeOnly.split(" ");
      if (allowed.includes(type)) el.removeAttribute("hidden"); else el.setAttribute("hidden", "");
    });
    editor.querySelectorAll("input[name=opt_correct]").forEach((box) => { box.type = type === "single" ? "radio" : "checkbox"; });
  };
  select.addEventListener("change", apply);
  apply();
  const add = editor.querySelector("[data-add-option]");
  if (add) add.addEventListener("click", () => {
    const hidden = editor.querySelector("[data-option-row][hidden]");
    if (hidden) hidden.removeAttribute("hidden");
  });
}

/* ---- CyberHero round editor -------------------------------------------- */
function initRoundEditor() {
  const editor = document.querySelector("[data-round-editor]");
  if (!editor) return;
  const select = editor.querySelector("select[name=round_type]");
  const apply = () => {
    const type = select.value;
    editor.querySelectorAll("[data-rtype-only]").forEach((el) => {
      if (el.dataset.rtypeOnly.split(" ").includes(type)) el.removeAttribute("hidden"); else el.setAttribute("hidden", "");
    });
  };
  select.addEventListener("change", apply);
  apply();
  const add = editor.querySelector("[data-add-item]");
  if (add) add.addEventListener("click", () => {
    const hidden = editor.querySelector("[data-item-row][hidden]");
    if (hidden) hidden.removeAttribute("hidden");
  });
}

/* ---- discussion reply targeting ----------------------------------------- */
function initReplies() {
  const hidden = document.querySelector("[data-reply-parent]");
  if (!hidden) return;
  document.querySelectorAll("[data-reply-to]").forEach((el) => {
    el.addEventListener("click", () => { hidden.value = el.dataset.replyTo; });
  });
}

/* ---- flash auto-dismiss ------------------------------------------------- */
function initFlash() {
  document.querySelectorAll(".flash-stack .alert-success, .flash-stack .alert-info").forEach((el) => {
    setTimeout(() => { el.classList.add("fade"); el.classList.remove("show"); setTimeout(() => el.remove(), 300); }, 6000);
  });
}

initTheme();
initMobileNav();
initSearch();
initLesson();
initConfirm();
initTabs();
initSortable();
initQuizTimer();
initNotifications();
initQuestionEditor();
initRoundEditor();
initReplies();
initFlash();
