// Cliente del API Gateway. La sesión viaja en cookie HttpOnly (la fija el gateway); aquí no se guarda ningún token.
var API_BASE = 'http://localhost:8000/api/v1';

var ERRORES = {
  400: 'Revisa los datos ingresados.',
  401: 'Tu sesión no es válida. Inicia sesión para continuar.',
  403: 'No tienes permiso para realizar esta acción.',
  404: 'No encontramos lo que buscas.',
  409: 'Ese dato ya está registrado o el estado no lo permite.',
  422: 'No se pudo completar por una regla del restaurante.',
  429: 'Demasiados intentos. Espera un momento e inténtalo de nuevo.'
};

async function api(path, opts) {
  opts = opts || {};
  var res;
  try {
    res = await fetch(API_BASE + path, Object.assign({ credentials: 'include', headers: { 'Content-Type': 'application/json' } }, opts));
  } catch (e) {
    throw { status: 0, message: 'No hay conexión con el servidor. Intenta nuevamente.' };
  }
  var data = null;
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) {
    var msg = ERRORES[res.status] || 'Hubo un problema. Intenta nuevamente.';
    // 422 por regla del negocio (fuera de zona, sin stock…): el backend manda un texto seguro en "detail"; si es validación, "detail" es una lista y se usa el genérico
    if (res.status === 422 && data && typeof data.detail === 'string') msg = data.detail;
    throw { status: res.status, message: msg };
  }
  return data;
}

function showAlert(id, msg, ok) {
  var el = document.getElementById(id);
  el.textContent = msg;
  el.className = 'alert ' + (ok ? 'alert-success' : 'alert-danger');
}

function validarRun(run) {
  run = String(run).replace(/[.\s]/g, '').toUpperCase();
  var m = /^(\d{7,8})-([\dK])$/.exec(run);
  if (!m) return false;
  var suma = 0, mult = 2;
  for (var i = m[1].length - 1; i >= 0; i--) { suma += parseInt(m[1][i], 10) * mult; mult = mult === 7 ? 2 : mult + 1; }
  var dv = 11 - (suma % 11);
  dv = dv === 11 ? '0' : dv === 10 ? 'K' : String(dv);
  return dv === m[2];
}
