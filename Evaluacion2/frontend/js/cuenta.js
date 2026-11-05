// Mi cuenta (P09). Usa el gateway: perfil (S07/S08), direcciones (S36-S39) y pedidos por GraphQL (misPedidos, anularPedido).
(function () {
  var clp = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });
  var MAX_DIR = 5;

  function fecha(iso) {
    try { return new Date(iso).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' }); }
    catch (e) { return iso || ''; }
  }

  // El cliente solo puede anular antes de que el pedido entre a cocina.
  function anulable(estado) { return estado === 'CREADO' || estado === 'PAGADO'; }

  function alCerrarSesion(err) {
    if (err && err.status === 401) { location.href = 'login.php'; return true; }
    return false;
  }

  // ---------------------------------------------------------------- Perfil
  var formPerfil = document.getElementById('form-perfil');
  var campos = ['pf-nombre', 'pf-sexo', 'pf-telefono'];
  var perfilOriginal = {};

  function pintarPerfil(p) {
    document.getElementById('pf-run').value = p.run || '';
    document.getElementById('pf-email').value = p.email || '';
    document.getElementById('pf-nombre').value = p.nombre || '';
    document.getElementById('pf-sexo').value = p.sexo || 'O';
    document.getElementById('pf-telefono').value = p.telefono || '';
    perfilOriginal = { nombre: p.nombre, sexo: p.sexo, telefono: p.telefono };
  }

  function modoEdicion(on) {
    campos.forEach(function (id) { document.getElementById(id).disabled = !on; });
    document.getElementById('perfil-acciones').classList.toggle('d-none', !on);
    document.getElementById('btn-editar-perfil').classList.toggle('d-none', on);
  }

  document.getElementById('btn-editar-perfil').addEventListener('click', function () { modoEdicion(true); });
  document.getElementById('btn-cancelar-perfil').addEventListener('click', function () {
    pintarPerfil(Object.assign({ run: document.getElementById('pf-run').value, email: document.getElementById('pf-email').value }, perfilOriginal));
    modoEdicion(false);
  });

  formPerfil.addEventListener('submit', async function (e) {
    e.preventDefault();
    var body = {
      nombre: document.getElementById('pf-nombre').value.trim(),
      sexo: document.getElementById('pf-sexo').value,
      telefono: document.getElementById('pf-telefono').value.trim()
    };
    try {
      var p = await api('/me', { method: 'PUT', body: JSON.stringify(body) });
      pintarPerfil(p); modoEdicion(false);
      showAlert('alerta', 'Datos actualizados.', true);
    } catch (err) { if (!alCerrarSesion(err)) showAlert('alerta', err.message, false); }
  });

  async function cargarPerfil() {
    try { pintarPerfil(await api('/me')); }
    catch (err) { if (!alCerrarSesion(err)) showAlert('alerta', err.message, false); }
  }

  // ---------------------------------------------------------------- Direcciones
  var cajaDir = document.getElementById('direcciones');
  var formDir = document.getElementById('form-dir');

  function pintarDirecciones(lista) {
    document.getElementById('dir-contador').textContent = '(' + lista.length + ' de ' + MAX_DIR + ')';
    document.getElementById('btn-nueva-dir').disabled = lista.length >= MAX_DIR;
    cajaDir.textContent = '';
    if (!lista.length) { cajaDir.innerHTML = '<p class="text-muted mb-0">Aún no tienes direcciones guardadas.</p>'; return; }
    lista.forEach(function (d) {
      var row = document.createElement('div');
      row.className = 'd-flex justify-content-between align-items-start border-bottom py-2 gap-2';
      var info = document.createElement('div');
      var titulo = document.createElement('strong');
      titulo.textContent = d.alias + (d.principal ? '' : '');
      info.append(titulo);
      if (d.principal) {
        var badge = document.createElement('span');
        badge.className = 'badge text-bg-success ms-2'; badge.textContent = 'Principal';
        info.append(badge);
      }
      var det = document.createElement('div');
      det.className = 'text-muted small';
      det.textContent = d.direccion + ', ' + d.comuna + ', ' + d.region;
      info.append(det);
      var acciones = document.createElement('div');
      acciones.className = 'd-flex gap-2 flex-shrink-0';
      if (!d.principal) {
        var btnPrin = document.createElement('button');
        btnPrin.className = 'btn btn-al-sahara-secundario btn-sm'; btnPrin.textContent = 'Hacer principal';
        btnPrin.addEventListener('click', function () { hacerPrincipal(d); });
        acciones.append(btnPrin);
      }
      var btnDel = document.createElement('button');
      btnDel.className = 'btn btn-al-sahara-oscuro btn-sm'; btnDel.textContent = 'Eliminar';
      btnDel.addEventListener('click', function () { borrarDireccion(d.id); });
      acciones.append(btnDel);
      row.append(info, acciones);
      cajaDir.append(row);
    });
  }

  async function cargarDirecciones() {
    try { pintarDirecciones(await api('/me/addresses')); }
    catch (err) { if (!alCerrarSesion(err)) cajaDir.innerHTML = '<p class="text-danger mb-0">' + err.message + '</p>'; }
  }

  document.getElementById('btn-nueva-dir').addEventListener('click', function () { formDir.classList.remove('d-none'); });
  document.getElementById('btn-cancelar-dir').addEventListener('click', function () { formDir.reset(); formDir.classList.add('d-none'); });

  formDir.addEventListener('submit', async function (e) {
    e.preventDefault();
    var body = {
      alias: document.getElementById('d-alias').value.trim() || 'Casa',
      direccion: document.getElementById('d-direccion').value.trim(),
      comuna: document.getElementById('d-comuna').value.trim(),
      provincia: document.getElementById('d-provincia').value.trim(),
      region: document.getElementById('d-region').value.trim(),
      principal: document.getElementById('d-principal').checked
    };
    try {
      await api('/me/addresses', { method: 'POST', body: JSON.stringify(body) });
      formDir.reset(); formDir.classList.add('d-none');
      showAlert('alerta', 'Dirección agregada.', true);
      cargarDirecciones();
    } catch (err) { if (!alCerrarSesion(err)) showAlert('alerta', err.message, false); }
  });

  async function hacerPrincipal(d) {
    try {
      await api('/me/addresses/' + d.id, { method: 'PUT', body: JSON.stringify({
        alias: d.alias, direccion: d.direccion, comuna: d.comuna, provincia: d.provincia, region: d.region, principal: true
      }) });
      cargarDirecciones();
    } catch (err) { if (!alCerrarSesion(err)) showAlert('alerta', err.message, false); }
  }

  async function borrarDireccion(id) {
    if (!confirm('¿Eliminar esta dirección?')) return;
    try { await api('/me/addresses/' + id, { method: 'DELETE' }); cargarDirecciones(); }
    catch (err) { if (!alCerrarSesion(err)) showAlert('alerta', err.message, false); }
  }

  // ---------------------------------------------------------------- Pedidos (GraphQL)
  var cajaPedidos = document.getElementById('pedidos');
  var LISTA = 'query($page:Int,$limit:Int){ misPedidos(page:$page,limit:$limit){ ' +
    'id estado tipo total creadoEn boleta{ numero } items{ cantidad nombre } } }';

  function pintarPedidos(lista) {
    cajaPedidos.textContent = '';
    if (!lista.length) { cajaPedidos.innerHTML = '<p class="text-muted mb-0">Todavía no tienes pedidos.</p>'; return; }
    lista.forEach(function (o) {
      var card = document.createElement('div');
      card.className = 'border rounded p-3 mb-2';

      var cab = document.createElement('div');
      cab.className = 'd-flex justify-content-between align-items-center flex-wrap gap-2';
      var izq = document.createElement('div');
      izq.innerHTML = '<strong>Pedido ' + o.id.slice(-6).toUpperCase() + '</strong> ' +
        '<span class="badge text-bg-secondary">' + o.estado + '</span>' +
        '<div class="text-muted small">' + fecha(o.creadoEn) + ' · ' + (o.tipo || '') + '</div>';
      var der = document.createElement('div');
      der.className = 'text-end';
      der.innerHTML = '<div class="al-sahara-total">' + clp.format(o.total) + '</div>';
      cab.append(izq, der);

      var detalle = document.createElement('div');
      detalle.className = 'text-muted small mt-2';
      detalle.textContent = o.items.map(function (i) { return i.cantidad + '× ' + i.nombre; }).join(', ');

      var pie = document.createElement('div');
      pie.className = 'd-flex gap-2 mt-2 flex-wrap';
      var verPago = document.createElement('a');
      verPago.className = 'btn btn-al-sahara-secundario btn-sm'; verPago.href = 'pago.php?order=' + o.id;
      verPago.textContent = o.estado === 'CREADO' ? 'Pagar / ver' : 'Ver detalle';
      pie.append(verPago);

      if (o.boleta) {
        var boleta = document.createElement('span');
        boleta.className = 'align-self-center small text-muted';
        boleta.textContent = 'Boleta N° ' + o.boleta.numero;
        pie.append(boleta);
      }
      if (anulable(o.estado)) {
        var btnAnular = document.createElement('button');
        btnAnular.className = 'btn btn-al-sahara-oscuro btn-sm'; btnAnular.textContent = 'Anular';
        btnAnular.addEventListener('click', function () { anular(o.id); });
        pie.append(btnAnular);
      }

      card.append(cab, detalle, pie);
      cajaPedidos.append(card);
    });
  }

  async function cargarPedidos() {
    try {
      var res = await api('/graphql', { method: 'POST', body: JSON.stringify({ query: LISTA, variables: { page: 1, limit: 20 } }) });
      if (res.errors) { cajaPedidos.innerHTML = '<p class="text-danger mb-0">No pudimos cargar tus pedidos.</p>'; return; }
      pintarPedidos((res.data && res.data.misPedidos) || []);
    } catch (err) { if (!alCerrarSesion(err)) cajaPedidos.innerHTML = '<p class="text-danger mb-0">' + err.message + '</p>'; }
  }

  async function anular(id) {
    var motivo = prompt('¿Por qué quieres anular este pedido?');
    if (motivo === null) return;
    motivo = motivo.trim();
    if (motivo.length < 3) { showAlert('alerta', 'Indica un motivo (mínimo 3 caracteres).', false); return; }
    var MUT = 'mutation($id:ID!,$motivo:String!){ anularPedido(id:$id,motivo:$motivo){ id estado motivoAnulacion } }';
    try {
      var res = await api('/graphql', { method: 'POST', body: JSON.stringify({ query: MUT, variables: { id: id, motivo: motivo } }) });
      if (res.errors || !(res.data && res.data.anularPedido)) {
        showAlert('alerta', 'No se pudo anular el pedido (puede que ya esté en cocina).', false); return;
      }
      showAlert('alerta', 'Pedido anulado.', true);
      cargarPedidos();
    } catch (err) { if (!alCerrarSesion(err)) showAlert('alerta', err.message, false); }
  }

  // ---------------------------------------------------------------- Arranque
  cargarPerfil();
  cargarDirecciones();
  cargarPedidos();
})();
