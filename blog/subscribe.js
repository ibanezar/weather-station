/* ═══════════════════════════════════════════════════════════
   Prijava na nove blog članke (dvojni opt-in prek Cloudflare Workerja).
   Samostojni widget — vstavi se pred footer.
   Vključi: <script src="/blog/subscribe.js" defer></script>
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";
  var PROXY = "https://weatherireica1.filip-eremita.workers.dev";

  var box = document.createElement("section");
  box.className = "subscribe-box";
  box.innerHTML =
    '<h2 class="sub-title">📬 Prijava na novičke</h2>' +
    '<p class="sub-desc">Prijavi se in ob vsakem novem članku (vremenski povzetki, rekordi, analize) dobiš e-obvestilo. Brez spama, odjava z enim klikom.</p>' +
    '<form class="sub-form" id="sub-form" autocomplete="off">' +
      '<input class="sub-input" id="sub-email" type="email" required maxlength="120" placeholder="tvoj@email.si" aria-label="E-naslov">' +
      '<input class="sub-hp" type="text" name="website" id="sub-hp" tabindex="-1" autocomplete="off" aria-hidden="true">' +
      '<button class="sub-btn" id="sub-btn" type="submit">Prijava</button>' +
    '</form>' +
    '<p class="sub-msg" id="sub-msg" aria-live="polite"></p>';

  var foot = document.querySelector(".site-foot");
  if (foot && foot.parentNode) foot.parentNode.insertBefore(box, foot);
  else (document.querySelector(".wrap") || document.body).appendChild(box);

  var form  = box.querySelector("#sub-form");
  var email = box.querySelector("#sub-email");
  var btn   = box.querySelector("#sub-btn");
  var msg   = box.querySelector("#sub-msg");

  function setMsg(t, err) { msg.textContent = t || ""; msg.className = "sub-msg" + (err ? " err" : " ok"); }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (box.querySelector("#sub-hp").value) return; // bot
    var val = email.value.trim();
    if (!val) { setMsg("Vpiši e-naslov.", true); return; }
    btn.disabled = true; btn.textContent = "Pošiljam…"; setMsg("");
    fetch(PROXY + "/blog-subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: val, website: "" })
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok || res.j.error) { setMsg(res.j.error || "Napaka pri prijavi.", true); return; }
        if (res.j.already) { setMsg("Ta e-naslov je že naročen. 🙂"); }
        else { setMsg("Skoraj gotovo! Preveri e-pošto in potrdi naročnino."); form.reset(); }
      })
      .catch(function () { setMsg("Napaka v povezavi. Poskusi znova.", true); })
      .then(function () { btn.disabled = false; btn.textContent = "Prijava"; });
  });
})();
