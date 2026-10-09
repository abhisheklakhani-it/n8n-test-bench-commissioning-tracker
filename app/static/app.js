// Small progressive enhancements. Every page also works without JavaScript.
(function () {
  "use strict";
  document.documentElement.classList.add("js");

  // "Are you sure?" for irreversible actions (forms with data-confirm).
  document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute && e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // Demo login: click a role to fill the form.
  document.querySelectorAll(".demo-user").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.getElementById("username").value = btn.dataset.username;
      document.getElementById("password").value = btn.dataset.password;
      document.getElementById("password").form.requestSubmit();
    });
  });

  // Print button (QR codes).
  var printBtn = document.getElementById("print-btn");
  if (printBtn) printBtn.addEventListener("click", function () { window.print(); });

  // PIN pad.
  var pin = document.getElementById("pin");
  if (pin) {
    var dots = document.querySelectorAll(".pin-dots span");
    var show = function () { dots.forEach(function (d, i) { d.classList.toggle("on", i < pin.value.length); }); };
    document.querySelectorAll(".key[data-digit]").forEach(function (k) {
      k.addEventListener("click", function () { if (pin.value.length < 6) pin.value += k.dataset.digit; show(); });
    });
    var del = document.querySelector(".key[data-del]");
    if (del) del.addEventListener("click", function () { pin.value = pin.value.slice(0, -1); show(); });
    show();
  }

  // Result form: checklist + measured values. "Done" only when everything is ticked and every value is
  // inside its tolerance (the server checks the same rules).
  var passBtn = document.getElementById("pass-btn");
  if (passBtn) {
    var form = passBtn.form;
    var boxes = Array.prototype.slice.call(form.querySelectorAll('input[name="check"]'));
    var measures = Array.prototype.slice.call(form.querySelectorAll(".measure"));
    var hint = document.getElementById("pass-hint");
    var update = function () {
      var allChecked = boxes.every(function (b) { return b.checked; });
      var allOk = measures.every(function (m) {
        var input = m.querySelector("input");
        var state = m.querySelector(".m-state");
        var text = input.value.trim().replace(",", ".");
        var value = text === "" ? NaN : Number(text);
        var ok = m.dataset.kind === "text" ? text !== "" : !isNaN(value) && value >= Number(m.dataset.min) && value <= Number(m.dataset.max);
        m.classList.toggle("ok", ok);
        m.classList.toggle("bad", text !== "" && !ok);
        state.textContent = text === "" ? "" : (ok ? "✓ OK" : "✗");
        return ok;
      });
      passBtn.disabled = !(allChecked && allOk);
      if (hint) hint.hidden = allChecked && allOk;
    };
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    update();
  }

  // Working-time clock on the shop-floor screen.
  var timer = document.querySelector(".timer[data-start]");
  if (timer && timer.dataset.start) {
    var started = Date.parse(timer.dataset.start);
    var pausedSeconds = Number(timer.dataset.paused || 0);
    var pausedAt = timer.dataset.pausedAt ? Date.parse(timer.dataset.pausedAt) : null;
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    var tick = function () {
      var end = pausedAt || Date.now();
      var s = Math.max(0, Math.floor((end - started) / 1000) - pausedSeconds);
      timer.textContent = pad(Math.floor(s / 3600)) + ":" + pad(Math.floor(s / 60) % 60) + ":" + pad(s % 60);
    };
    tick();
    if (!pausedAt) window.setInterval(tick, 1000);
  }

  // Sound for new tasks (browsers only allow audio after the first touch on the page).
  var audio = null;
  document.addEventListener("pointerdown", function () {
    if (!audio && (window.AudioContext || window.webkitAudioContext)) audio = new (window.AudioContext || window.webkitAudioContext)();
  }, { once: true });
  function beep() {
    if (navigator.vibrate) navigator.vibrate([300, 150, 300]);
    if (!audio) return;
    [0, 0.35].forEach(function (offset) {
      var o = audio.createOscillator(), g = audio.createGain();
      o.frequency.value = 880; o.connect(g); g.connect(audio.destination);
      g.gain.setValueAtTime(0.25, audio.currentTime + offset);
      o.start(audio.currentTime + offset); o.stop(audio.currentTime + offset + 0.25);
    });
  }

  // Live updates every 10-15 s: bell counter, dashboards, and new tasks on the shop floor
  // (never while the user is typing in a form).
  var badge = document.getElementById("badge");
  var shop = document.querySelector("[data-shop]");
  if (!badge && !shop) return;
  var version = null;
  var openTasks = shop ? Number(shop.dataset.open || 0) : 0;
  var dirty = false;
  document.addEventListener("input", function () { dirty = true; });
  function poll() {
    fetch("/api/status", { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.auth) return;
        if (badge) { badge.textContent = data.badge; badge.hidden = !data.badge; }
        if (shop && data.open > openTasks && !dirty) {
          beep();
          window.setTimeout(function () { window.location.href = "/werker/aufgabe?neu=1"; }, 1200);
          return;
        }
        if (shop) openTasks = data.open;
        if (version !== null && data.v !== version && document.body.dataset.autorefresh && !dirty) window.location.reload();
        version = data.v;
      })
      .catch(function () { /* offline: try again next time */ });
  }
  poll();
  window.setInterval(poll, shop ? 10000 : 15000);
})();
