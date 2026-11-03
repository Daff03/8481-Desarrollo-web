(function () {
  var form = document.getElementById('form-registro');
  var btn = document.getElementById('btn-registro');

  var reglas = {
    run: function (v) { return validarRun(v); },
    nombre: function (v) { return v.trim().split(/\s+/).length >= 2; },
    direccion: function (v) { return v.trim().length >= 5; },
    comuna: function (v) { return v.trim().length >= 2; },
    provincia: function (v) { return v.trim().length >= 2; },
    region: function (v) { return v.trim().length >= 2; },
    fechaNacimiento: function (v) {
      if (!v) return false;
      var d = new Date(v), hoy = new Date();
      var edad = hoy.getFullYear() - d.getFullYear() - (hoy < new Date(hoy.getFullYear(), d.getMonth(), d.getDate()) ? 1 : 0);
      return edad >= 18 && edad < 120;
    },
    sexo: function (v) { return v !== ''; },
    telefono: function (v) { return /^\+?\d{9,12}$/.test(v.replace(/\s/g, '')); },
    email: function (v) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); },
    password: function (v) { return v.length >= 8 && /[A-Za-z]/.test(v) && /\d/.test(v); }
  };

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var ok = true, datos = {};
    Object.keys(reglas).forEach(function (k) {
      var campo = form.elements[k];
      var valido = reglas[k](campo.value);
      campo.classList.toggle('is-invalid', !valido);
      if (!valido) ok = false;
      datos[k] = campo.value.trim();
    });
    if (!ok) { showAlert('alerta', 'Revisa los campos marcados.', false); return; }

    btn.disabled = true;
    try {
      await api('/auth/register', { method: 'POST', body: JSON.stringify(datos) });
      form.reset();
      showAlert('alerta', 'Cuenta creada. Revisa tu correo para confirmarlo antes de iniciar sesión.', true);
    } catch (err) {
      showAlert('alerta', err.message, false);
    } finally { btn.disabled = false; }
  });
})();
