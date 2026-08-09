// その手があったか — 制作アーカイブ（build_site.py が生成）
(function () {
  // ---- コピー ----
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) {}
    try {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', '');
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      var ok = document.execCommand('copy');
      ta.remove(); return ok;
    } catch (e) { return false; }
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]');
    if (!btn) return;
    var src = document.getElementById(btn.getAttribute('data-copy'));
    if (!src) return;
    var text = ('value' in src && src.tagName === 'TEXTAREA') ? src.value : src.textContent;
    copyText(text).then(function (ok) {
      var orig = btn.textContent;
      btn.textContent = ok ? 'コピーしました ✓' : 'コピーできませんでした';
      btn.classList.add('copied');
      setTimeout(function () { btn.textContent = orig; btn.classList.remove('copied'); }, 1800);
    });
  });

  // ---- テーマ切り替え（自動 → ライト → ダーク） ----
  var KEY = 'sonote-theme';
  var btn = document.getElementById('themeBtn');
  function label(mode) {
    return 'テーマ：' + (mode === 'light' ? 'ライト' : mode === 'dark' ? 'ダーク' : '自動');
  }
  function current() {
    try { return localStorage.getItem(KEY) || 'auto'; } catch (e) { return 'auto'; }
  }
  function apply(mode) {
    if (mode === 'light' || mode === 'dark') {
      document.documentElement.setAttribute('data-theme', mode);
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    if (btn) btn.textContent = label(mode);
  }
  if (btn) {
    apply(current());
    btn.addEventListener('click', function () {
      var next = { auto: 'light', light: 'dark', dark: 'auto' }[current()] || 'auto';
      try { localStorage.setItem(KEY, next); } catch (e) {}
      apply(next);
    });
  }
})();
