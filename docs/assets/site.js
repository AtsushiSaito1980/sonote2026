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
  // note のエディタは書式付きの貼り付けを受け取れるので、HTML も一緒にクリップボードへ置く。
  // 見出し・太字・引用・箇条書きがそのまま入る（失敗したらプレーンに落とす）
  // 戻り値は 'rich'（書式つきで入った）／'plain'（書式なしに落ちた）／false（失敗）
  async function copyRich(html, text) {
    try {
      await navigator.clipboard.write([new ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([text], { type: 'text/plain' }),
      })]);
      return 'rich';
    } catch (e) {}
    return (await copyText(text)) ? 'plain' : false;
  }
  function srcText(id) {
    var el = document.getElementById(id);
    if (!el) return '';
    return ('value' in el && el.tagName === 'TEXTAREA') ? el.value : el.textContent;
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]');
    if (!btn) return;
    var src = document.getElementById(btn.getAttribute('data-copy'));
    if (!src) return;
    var text = ('value' in src && src.tagName === 'TEXTAREA') ? src.value : src.textContent;
    var htmlId = btn.getAttribute('data-copy-html');
    var run = htmlId ? copyRich(srcText(htmlId), text) : copyText(text);
    run.then(function (ok) {
      var orig = btn.textContent;
      // 書式つきで入ったのか、素のテキストに落ちたのかを隠さずに出す
      btn.textContent = ok === 'rich' ? '書式つきでコピーしました ✓'
                      : ok === 'plain' ? '書式なしでコピーしました（見出しは手で設定）'
                      : ok ? 'コピーしました ✓' : 'コピーできませんでした';
      btn.classList.add('copied');
      setTimeout(function () { btn.textContent = orig; btn.classList.remove('copied'); }, 2600);
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
