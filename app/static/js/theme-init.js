/* Runs synchronously in <head> before first paint so the chosen theme never
   flashes. Stored preference: localStorage "elearning.theme" = light|dark|system. */
(function () {
  var KEY = "elearning.theme";
  var pref = "system";
  try { pref = localStorage.getItem(KEY) || "system"; } catch (e) { /* storage blocked */ }
  if (pref !== "light" && pref !== "dark") { pref = "system"; }
  var dark = true;
  if (pref === "system") {
    try { dark = !window.matchMedia("(prefers-color-scheme: light)").matches; } catch (e) { dark = true; }
  } else {
    dark = pref === "dark";
  }
  var root = document.documentElement;
  root.setAttribute("data-theme", dark ? "dark" : "light");
  root.setAttribute("data-theme-pref", pref);
})();
