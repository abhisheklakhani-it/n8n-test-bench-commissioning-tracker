// Small progressive enhancements. Every page also works without JavaScript.
(function () {
  "use strict";

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

  // Checklist: the "Done" button is only active when every item is ticked (server checks too).
  var passBtn = document.getElementById("pass-btn");
  if (passBtn) {
    var boxes = Array.prototype.slice.call(document.querySelectorAll('.result-form input[name="check"]'));
    var hint = document.getElementById("pass-hint");
    var update = function () {
      var all = boxes.every(function (b) { return b.checked; });
      passBtn.disabled = !all;
      if (hint) hint.hidden = all;
    };
    boxes.forEach(function (b) { b.addEventListener("change", update); });
    update();
  }

  // Live updates: bell counter every 15 s; dashboards reload when something changed
  // (never while the user is typing in a form).
  var badge = document.getElementById("badge");
  if (!badge) return;
  var version = null;
  var dirty = false;
  document.addEventListener("input", function () { dirty = true; });
  function poll() {
    fetch("/api/status", { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.auth) return;
        badge.textContent = data.badge;
        badge.hidden = !data.badge;
        if (version !== null && data.v !== version && document.body.dataset.autorefresh && !dirty) {
          window.location.reload();
        }
        version = data.v;
      })
      .catch(function () { /* offline: try again next time */ });
  }
  poll();
  window.setInterval(poll, 15000);
})();
