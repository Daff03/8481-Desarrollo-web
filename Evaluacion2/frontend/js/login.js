(function () {
  var form = document.getElementById('form-login');
  var btn = document.getElementById('btn-login');
  var destino = new URLSearchParams(location.search).get('next');
  var permitidos = ['pedido.php', 'index.php', 'cuenta.php'];

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var email = form.elements.email, pass = form.elements.password;
    var okEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value);
    email.classList.toggle('is-invalid', !okEmail);
    pass.classList.toggle('is-invalid', !pass.value);
    if (!okEmail || !pass.value) return;

    btn.disabled = true;
    try {
      await api('/auth/login', { method: 'POST', body: JSON.stringify({ email: email.value.trim(), password: pass.value }) });
      location.href = permitidos.indexOf(destino) !== -1 ? destino : 'index.php';
    } catch (err) {
      showAlert('alerta', err.status === 401 ? 'Correo o contraseña incorrectos.' : err.message, false);
    } finally { btn.disabled = false; }
  });
})();
