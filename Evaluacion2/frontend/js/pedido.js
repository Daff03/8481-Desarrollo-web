(function () {
  var KEY = 'alSaharaCart'; // { "productId": cantidad } — sin precios: el servidor los calcula
  var cart = JSON.parse(localStorage.getItem(KEY) || '{}');
  var productos = {};
  var box = document.getElementById('carrito');
  var form = document.getElementById('form-pedido');
  var btn = document.getElementById('btn-pedido');
  var clp = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });

  function guardar() { localStorage.setItem(KEY, JSON.stringify(cart)); }

  function pintar() {
    box.textContent = '';
    var ids = Object.keys(cart).filter(function (id) { return productos[id]; });
    document.getElementById('vacio').classList.toggle('d-none', ids.length > 0);
    form.classList.toggle('d-none', ids.length === 0);
    var total = 0;
    ids.forEach(function (id) {
      var p = productos[id], q = cart[id];
      total += p.precio * q;
      var row = document.createElement('div'); row.className = 'al-sahara-cart-row';
      var nombre = document.createElement('div'); nombre.className = 'flex-grow-1'; nombre.textContent = p.nombre;
      var precio = document.createElement('div'); precio.textContent = clp.format(p.precio);
      var inp = document.createElement('input');
      inp.type = 'number'; inp.min = 1; inp.max = 20; inp.value = q; inp.className = 'form-control qty';
      inp.setAttribute('aria-label', 'Cantidad de ' + p.nombre);
      inp.addEventListener('change', function () {
        var n = Math.max(1, Math.min(20, parseInt(inp.value, 10) || 1));
        cart[id] = n; guardar(); pintar();
      });
      var del = document.createElement('button');
      del.type = 'button'; del.className = 'btn btn-sm btn-outline-secondary'; del.textContent = 'Quitar';
      del.addEventListener('click', function () { delete cart[id]; guardar(); pintar(); });
      row.append(nombre, precio, inp, del); box.append(row);
    });
    document.getElementById('total').textContent = clp.format(total);
  }

  async function iniciar() {
    try {
      var lista = await api('/products?available=true');
      lista.forEach(function (p) { productos[p.id] = p; });
      Object.keys(cart).forEach(function (id) { if (!productos[id]) delete cart[id]; }); // platos que ya no están disponibles
      guardar(); pintar();
    } catch (err) { showAlert('alerta', err.message, false); }
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var dir = form.elements.direccion, com = form.elements.comuna;
    dir.classList.toggle('is-invalid', dir.value.trim().length < 5);
    com.classList.toggle('is-invalid', com.value.trim().length < 2);
    if (dir.value.trim().length < 5 || com.value.trim().length < 2) return;

    btn.disabled = true;
    try {
      var zona = await api('/delivery/coverage?comuna=' + encodeURIComponent(com.value.trim()));
      if (!zona.cubierta) { showAlert('alerta', 'Esa comuna está fuera de la zona de entrega (3 km del local).', false); return; }
      var items = Object.keys(cart).map(function (id) { return { productId: Number(id), cantidad: cart[id] }; });
      var orden = await api('/orders', { method: 'POST', body: JSON.stringify({
        items: items, direccionEntrega: dir.value.trim() + ', ' + com.value.trim(), comentario: form.elements.comentario.value.trim()
      }) });
      localStorage.removeItem(KEY);
      location.href = 'pago.php?order=' + encodeURIComponent(orden.id); // pantalla P08 (siguiente entrega)
    } catch (err) {
      if (err.status === 401) { location.href = 'login.php?next=pedido.php'; return; }
      showAlert('alerta', err.message, false);
    } finally { btn.disabled = false; }
  });

  iniciar();
})();
