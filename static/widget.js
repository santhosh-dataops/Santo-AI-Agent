/* Santo embeddable chat bubble.
   Usage: <script src="https://YOUR-HOST/widget.js" data-agent="acme-support"></script>
   Optional: data-position="left", data-title="Need help?" */
(function () {
  var script = document.currentScript;
  var agentId = script.getAttribute('data-agent');
  var origin = new URL(script.src).origin;
  var left = script.getAttribute('data-position') === 'left';
  var sessionKey = 'santo_session_' + agentId, session = null;
  try { session = sessionStorage.getItem(sessionKey); } catch (e) {}

  var host = document.createElement('div');
  host.style.cssText = 'position:fixed;bottom:20px;' + (left ? 'left' : 'right') + ':20px;z-index:2147483000';
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: 'open' });

  fetch(origin + '/api/agents/' + agentId).then(function (r) { return r.json(); }).then(function (a) {
    var c = a.theme_color || '#2563eb';
    root.innerHTML =
      '<style>' +
      '*{box-sizing:border-box;font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}' +
      '.btn{width:58px;height:58px;border-radius:50%;border:0;background:' + c + ';color:#fff;font-size:26px;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.25)}' +
      '.panel{display:none;position:absolute;bottom:72px;' + (left ? 'left' : 'right') + ':0;width:360px;max-width:calc(100vw - 40px);height:520px;max-height:calc(100vh - 110px);background:#fff;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.25);flex-direction:column;overflow:hidden}' +
      '.panel.open{display:flex}.hd{background:' + c + ';color:#fff;padding:14px 16px;font-weight:600}' +
      '.hd small{display:block;font-weight:400;opacity:.85}.log{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f7f7f8}' +
      '.m{max-width:85%;padding:8px 12px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}' +
      '.b{background:#fff;border:1px solid #e5e7eb;align-self:flex-start}.u{background:' + c + ';color:#fff;align-self:flex-end}' +
      'form{display:flex;gap:6px;padding:10px;border-top:1px solid #e5e7eb}input{flex:1;padding:9px 12px;border:1px solid #e5e7eb;border-radius:10px}' +
      'form button{border:0;background:' + c + ';color:#fff;border-radius:10px;padding:0 14px;cursor:pointer}' +
      '.pw{font-size:11px;text-align:center;padding:0 0 8px;color:#545C7A}.pw a{color:inherit}' +
      '</style>' +
      '<div class="panel"><div class="hd"></div><div class="log"></div>' +
      '<form><input placeholder="Type a message…"><button>Send</button></form>' +
      '<div class="pw">Powered by <a href="' + origin + '" target="_blank" rel="noopener">Santo</a></div></div>' +
      '<button class="btn" aria-label="Open chat">💬</button>';
    var panel = root.querySelector('.panel'), log = root.querySelector('.log'), input = root.querySelector('input');
    var hd = root.querySelector('.hd');
    hd.textContent = script.getAttribute('data-title') || a.name;
    if (a.business && a.business !== hd.textContent) { var sub = document.createElement('small'); sub.textContent = a.business; hd.appendChild(sub); }

    function add(cls, t) { var d = document.createElement('div'); d.className = 'm ' + cls; d.textContent = t; log.appendChild(d); log.scrollTop = 1e9; return d; }
    add('b', a.greeting);
    root.querySelector('.btn').onclick = function () { panel.classList.toggle('open'); input.focus(); };
    root.querySelector('form').onsubmit = function (e) {
      e.preventDefault(); var t = input.value.trim(); if (!t) return;
      add('u', t); input.value = ''; var w = add('b', '…');
      fetch(origin + '/api/agents/' + agentId + '/chat', { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ message: t, session_id: session }) })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.detail); return j; }); })
        .then(function (j) { session = j.session_id; try { sessionStorage.setItem(sessionKey, session); } catch (e) {} w.textContent = j.reply; })
        .catch(function (err) { w.textContent = 'Sorry, something went wrong. ' + (err.message || ''); });
    };
  });
})();
