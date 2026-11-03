/* Laboratorij: stikalo teme in širine. Izbira se hrani v localStorage (z varovalko: brez njega vse deluje). */
(function () {
  var root = document.documentElement;
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  var theme = get('lab-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  root.setAttribute('data-theme', theme);
  function wire(group, apply, saved) {
    var btns = document.querySelectorAll('[data-lab-' + group + ']');
    function mark(v) { btns.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-lab-' + group) === v)); }); }
    btns.forEach(function (b) { b.addEventListener('click', function () { var v = b.getAttribute('data-lab-' + group); apply(v); mark(v); set('lab-' + group, v); }); });
    apply(saved); mark(saved);
  }
  document.addEventListener('DOMContentLoaded', function () {
    wire('theme', function (v) { root.setAttribute('data-theme', v); }, theme);
    var frame = document.querySelector('.lab-frame');
    if (frame) wire('w', function (v) { frame.setAttribute('data-w', v); }, get('lab-w') || 'full');
  });
})();
