(function () {
  var token = new URLSearchParams(location.search).get('token');
  if (!token) { showAlert('alerta', 'El enlace no es válido.', false); return; }
  // El token va en el cuerpo (POST), nunca en la URL de la API.
  api('/auth/verify-email', { method: 'POST', body: JSON.stringify({ token: token }) })
    .then(function () {
      showAlert('alerta', 'Correo confirmado. Ya puedes iniciar sesión.', true);
      document.getElementById('ir-login').classList.remove('d-none');
      history.replaceState(null, '', 'verificar.php'); // saca el token de la barra de direcciones
    })
    .catch(function (err) {
      showAlert('alerta', err.status === 400 ? 'El enlace es inválido o ya venció. Regístrate nuevamente.' : err.message, false);
    });
})();
