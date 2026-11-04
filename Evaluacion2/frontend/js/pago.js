(function () {
  var params = new URLSearchParams(location.search);
  var orderId = params.get('order');
  var volvio = params.get('estado') !== null; // el parámetro solo indica que el usuario volvió de la pasarela; nunca se usa como prueba de pago
  var box = document.getElementById('resumen');
  var btn = document.getElementById('btn-pagar');
  var clp = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });

  if (!/^[0-9a-f]{24}$/.test(orderId || '')) { showAlert('alerta', 'No encontramos el pedido.', false); return; }

  // Una sola consulta GraphQL combina orders (pedido), inventory (ficha del plato) y payments (estado del pago).
  var RESUMEN = 'query($id: ID!){ resumenPedido(id: $id){ id estado total motivoAnulacion ' +
    'items{ nombre cantidad subtotal producto{ imagen } } pago{ estado } boleta{ numero } } }';

  function pintar(o) {
    box.textContent = '';
    o.items.forEach(function (i) {
      var row = document.createElement('div'); row.className = 'd-flex align-items-center gap-2 border-bottom py-1';
      if (i.producto && i.producto.imagen) {
        var img = document.createElement('img'); img.src = i.producto.imagen; img.alt = ''; img.width = 48; img.height = 32;
        img.className = 'rounded'; img.style.objectFit = 'cover'; row.append(img);
      }
      var a = document.createElement('span'); a.className = 'flex-grow-1'; a.textContent = i.cantidad + ' × ' + i.nombre;
      var b = document.createElement('span'); b.textContent = clp.format(i.subtotal);
      row.append(a, b); box.append(row);
    });
    document.getElementById('total').textContent = clp.format(o.total);
    btn.classList.toggle('d-none', o.estado !== 'CREADO');
    if (o.estado === 'CREADO') {
      var rechazado = o.pago && o.pago.estado === 'RECHAZADO';
      showAlert('alerta', rechazado ? 'El proveedor rechazó el pago. Puedes intentarlo nuevamente.' :
        volvio ? 'Aún no recibimos la confirmación del pago.' : 'Tu pedido está creado. Falta el pago para enviarlo a cocina.', !volvio && !rechazado);
    } else if (o.estado === 'CANCELADO') {
      showAlert('alerta', 'Este pedido fue anulado' + (o.motivoAnulacion ? ': ' + o.motivoAnulacion : '.'), false);
    } else {
      showAlert('alerta', '¡Pago confirmado! Tu pedido está en proceso.', true);
      if (o.boleta) {
        var p = document.getElementById('boleta'); p.classList.remove('d-none');
        p.textContent = 'Boleta N° ' + o.boleta.numero + '. Te la enviamos por correo.';
      }
    }
  }

  async function cargar() {
    try {
      var res = await api('/graphql', { method: 'POST', body: JSON.stringify({ query: RESUMEN, variables: { id: orderId } }) });
      var o = res.data && res.data.resumenPedido;
      if (!o) { showAlert('alerta', 'No encontramos ese pedido.', false); return null; }
      pintar(o); // si inventory o payments fallaron, llegan nulos (error parcial) y el resto se muestra igual
      return o;
    } catch (err) {
      if (err.status === 401) { location.href = 'login.php'; return null; }
      showAlert('alerta', err.message, false); return null;
    }
  }

  // Al volver de la pasarela, el aviso del proveedor llega al backend de forma asíncrona: se consulta hasta que cambie el estado.
  async function esperarConfirmacion(intentos) {
    var o = await cargar();
    if (o && o.estado === 'CREADO' && !(o.pago && o.pago.estado === 'RECHAZADO') && intentos > 0) {
      setTimeout(function () { esperarConfirmacion(intentos - 1); }, 1500);
    }
  }

  btn.addEventListener('click', async function () {
    btn.disabled = true;
    try {
      var pago = await api('/payments', { method: 'POST', body: JSON.stringify({ orderId: orderId }) });
      location.href = pago.checkoutUrl;
    } catch (err) {
      showAlert('alerta', err.status === 409 ? 'Este pedido ya no admite pago.' : err.message, false);
      btn.disabled = false;
    }
  });

  if (volvio) esperarConfirmacion(13); else cargar();
})();
