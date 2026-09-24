/* Runs synchronously in <head> before first paint so the chosen theme never
   flashes. Stored preference: localStorage "elearning.theme" = light|dark|system.
   Light is the default; "dark" and "system" are explicit choices. */
(function () {
  var KEY = "elearning.theme";
  var pref = "light";
  try { pref = localStorage.getItem(KEY) || "light"; } catch (e) { /* storage blocked */ }
  if (pref !== "dark" && pref !== "system") { pref = "light"; }
  var dark = false;
  if (pref === "system") {
    try { dark = window.matchMedia("(prefers-color-scheme: dark)").matches; } catch (e) { dark = false; }
  } else {
    dark = pref === "dark";
  }
  var root = document.documentElement;
  root.setAttribute("data-theme", dark ? "dark" : "light");
  root.setAttribute("data-theme-pref", pref);
})();
