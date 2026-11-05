const passwordToggle = document.getElementById('corePasswordToggle');
passwordToggle.addEventListener('click', function () {
  const field = document.getElementById('loginPassword');
  const visible = field.type === 'password';
  field.type = visible ? 'text' : 'password';
  passwordToggle.setAttribute('aria-pressed', String(visible));
  passwordToggle.textContent = visible ? 'إخفاء' : 'إظهار';
});
document.getElementById('coreLoginForm').addEventListener('submit', function () {
  this.querySelector('[type="submit"]').disabled = true;
  document.getElementById('coreLoginStatus').textContent = 'جارٍ تسجيل الدخول…';
});
window.addEventListener('pageshow', function () {
 document.querySelector('#coreLoginForm [type="submit"]').disabled = false;
 document.getElementById('coreLoginStatus').textContent = '';
});
