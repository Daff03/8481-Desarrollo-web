// RF14: la reserva se envía al backend vía API Gateway (ya no por WhatsApp). Requiere js/api.js cargado antes.
(function () {
  var form = document.getElementById('form-reserva');
  if (!form) return;
  var btn = document.getElementById('btn-reserva');
  var ok = document.getElementById('alerta-exito');
  var err = document.getElementById('alerta-error');

  function pad(n) { return String(n).padStart(2, '0'); }
  var ahora = new Date();
  form.elements.fecha.min = ahora.getFullYear() + '-' + pad(ahora.getMonth() + 1) + '-' + pad(ahora.getDate()) + 'T' + pad(ahora.getHours()) + ':' + pad(ahora.getMinutes());

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    ok.classList.add('d-none'); err.classList.add('d-none');

    var f = form.elements;
    var validos = {
      nombre: f.nombre.value.trim().split(/\s+/).length >= 2,
      email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.value),
      fecha: f.fecha.value !== '' && new Date(f.fecha.value) > new Date()
    };
    var todoOk = true;
    Object.keys(validos).forEach(function (k) {
      f[k].classList.toggle('is-invalid', !validos[k]);
      if (!validos[k]) todoOk = false;
    });
    if (!todoOk) return;

    btn.disabled = true;
    try {
      await api('/reservations', { method: 'POST', body: JSON.stringify({
        nombre: f.nombre.value.trim(),
        personas: Number(f.personas.value),
        email: f.email.value.trim(),
        fechaHora: f.fecha.value,
        mensaje: f.mensaje.value.trim()
      }) });
      form.reset();
      ok.classList.remove('d-none');
    } catch (e2) {
      err.textContent = e2.message;
      err.classList.remove('d-none');
    } finally { btn.disabled = false; }
  });
})();
