/* Core pages: progressive feedback, server remains authoritative. */
(function () {
  'use strict';
  const workspace = document.querySelector('[data-view-user]');
  if (workspace) document.querySelectorAll('[data-view-collection]').forEach(function (collection) {
    const toolbar = collection.querySelector('.core-view-toolbar');
    const buttons = Array.from(toolbar.querySelectorAll('[data-view]'));
    const key = 'core:view:' + workspace.dataset.viewUser + ':' + collection.dataset.viewCollection;
    const cards = collection.querySelector('.core-record-grid');
    const table = collection.querySelector('.core-table-wrap');
    function show(mode) {
      if (!buttons.some(function (button) { return button.dataset.view === mode; })) mode = 'cards';
      collection.dataset.viewMode = mode;
      if (cards) cards.hidden = mode !== 'cards';
      if (table) table.hidden = mode === 'cards';
      buttons.forEach(function (button) { button.setAttribute('aria-pressed', String(button.dataset.view === mode)); });
    }
    let saved;
    try { saved = localStorage.getItem(key); } catch (_) { /* Storage may be unavailable. */ }
    show(saved || 'cards');
    toolbar.hidden = false;
    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        show(button.dataset.view);
        try { localStorage.setItem(key, button.dataset.view); } catch (_) { /* The current view still works. */ }
      });
    });
  });
  const badge = document.getElementById('coreUnreadCount');
  let lastCount = null, notificationAudio = null;
  if (document.documentElement?.dataset.sound === 'true') {
    window.addEventListener('pointerdown', function () {
      try { notificationAudio = new (window.AudioContext || window.webkitAudioContext)(); notificationAudio.resume(); } catch (_) {}
    }, {once: true});
  }
  async function updateCount() {
    if (!badge || document.hidden) return;
    try {
      const response = await fetch('/notifications/ajax/bell/', {credentials: 'same-origin', headers: {'Accept': 'application/json'}});
      if (!response.ok || !response.headers.get('content-type').includes('application/json')) return;
      const data = await response.json(); badge.textContent = data.count;
      if (lastCount !== null && data.count > lastCount && notificationAudio && document.documentElement.dataset.quiet !== 'true') {
        try {
          const tone = notificationAudio.createOscillator(), gain = notificationAudio.createGain();
          tone.frequency.value = 660; gain.gain.value = 0.035;
          tone.connect(gain); gain.connect(notificationAudio.destination);
          tone.start(); tone.stop(notificationAudio.currentTime + 0.12);
        } catch (_) { /* Browsers may suspend audio; notification delivery is unaffected. */ }
      }
      lastCount = data.count;
    } catch (_) { /* Keep the last confirmed count on a network error. */ }
  }
  if (badge) { updateCount(); setInterval(updateCount, 60000); }
  window.addEventListener('pageshow', function (event) { if (event.persisted) window.location.reload(); });
})();
(function () {
  document.querySelectorAll('[data-open-dialog]').forEach(function (button) {
    button.addEventListener('click', function () {
      const dialog = document.getElementById(button.dataset.openDialog);
      if (dialog) { dialog.showModal(); dialog.dataset.opener = ''; }
      const menu = button.closest('.core-action-menu');
      if (menu) menu.open = false;
    });
  });
  document.querySelectorAll('[data-close-dialog]').forEach(function (button) {
    button.addEventListener('click', function () { button.closest('dialog').close(); });
  });
  document.querySelectorAll('.core-dialog').forEach(function (dialog) {
    dialog.addEventListener('click', function (event) {
      if (event.target !== dialog) return;
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    });
  });
})();
/* Keep entered values and the open dialog when server-side validation fails. */
document.querySelectorAll('.core-workspace form[method="post"]').forEach(function (form) {
  form.addEventListener('submit', async function (event) {
    event.preventDefault();
    if (form.dataset.pendingRequest) return;
    form.dataset.pendingRequest = 'true';
    const status = form.querySelector('[data-form-status]') || document.createElement('p');
    status.setAttribute('data-form-status', '');
    if (!status.parentElement) form.appendChild(status);
    status.setAttribute('role', 'status');
    status.textContent = 'جارٍ حفظ التغييرات…';
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, 30000);
    const buttons = Array.from(form.querySelectorAll('button'), function (button) {
      return {button: button, disabled: button.disabled};
    });
    try {
      // Named controls (such as the hidden "action") can mask form properties.
      const action = (event.submitter && event.submitter.getAttribute('formaction')) ?? form.getAttribute('action');
      const url = action ? new URL(action, document.baseURI).href : window.location.href;
      const data = new FormData(form);
      if (event.submitter && event.submitter.name) {
        data.append(event.submitter.name, event.submitter.value);
      }
      form.setAttribute('aria-busy', 'true');
      buttons.forEach(function (control) { control.button.disabled = true; });
      const result = await fetch(url, {
        method: 'POST', body: data, credentials: 'same-origin', signal: controller.signal
      });
      if (result.ok) { window.location.assign(result.url); return; }
      const html = new DOMParser().parseFromString(await result.text(), 'text/html');
      const message = html.querySelector('[role="alert"]');
      status.textContent = message ? message.textContent.trim() : 'تعذر حفظ التغييرات. تحقق من البيانات والصلاحيات ثم أعد المحاولة.';
      status.setAttribute('role', 'alert');
    } catch (_) {
      status.textContent = 'تعذر تأكيد نتيجة العملية. تحقق من الاتصال ثم حدّث الصفحة قبل إعادة الإرسال.';
      status.setAttribute('role', 'alert');
    } finally {
      clearTimeout(timer);
      delete form.dataset.pendingRequest;
      form.setAttribute('aria-busy', 'false');
      buttons.forEach(function (control) { control.button.disabled = control.disabled; });
    }
  });
});
