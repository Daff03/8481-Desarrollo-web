<?php $base = $base ?? ''; ?>
<header class="navbar navbar-expand-lg fixed-top py-3" id="alSaharaNavbar">
  <div class="container">

    <a class="navbar-brand d-flex align-items-center gap-2" href="<?= $base ?>#inicio">
      <span class="al-sahara-logo-icon">✦</span>
      <span class="d-flex flex-column lh-1">
        <span class="al-sahara-logo-name">Al Sahara</span>
        <span class="al-sahara-logo-sub">Restaurante</span>
      </span>
    </a>

    <button class="navbar-toggler border-0 shadow-none" type="button"
            data-bs-toggle="collapse" data-bs-target="#navAlSahara"
            aria-controls="navAlSahara" aria-expanded="false" aria-label="Abrir menú">
      <span class="navbar-toggler-icon"></span>
    </button>

    <div class="collapse navbar-collapse" id="navAlSahara">
      <ul class="navbar-nav mx-lg-auto gap-lg-4 text-center py-3 py-lg-0">
        <li class="nav-item"><a class="nav-link" href="<?= $base ?>#inicio">Inicio</a></li>
        <li class="nav-item"><a class="nav-link" href="<?= $base ?>#menu">Menú</a></li>
        <li class="nav-item"><a class="nav-link" href="<?= $base ?>#historia">Nuestra Historia</a></li>
        <li class="nav-item"><a class="nav-link" href="<?= $base ?>#contacto">Contacto</a></li>
      </ul>
      <div class="d-flex flex-column flex-lg-row gap-2 align-items-center">
        <a href="<?= $base ?>#contacto" class="btn btn-al-sahara-secundario px-4">Reservar Mesa</a>
        <a href="pedido.php" class="btn btn-al-sahara-primario px-4" aria-label="Ver carrito">Carrito (<span id="cartCount">0</span>)</a>
        <a href="login.php" id="btnIngresar" class="btn btn-al-sahara-oscuro px-4">Ingresar</a>
        <div id="sesionBox" class="d-none flex-column flex-lg-row gap-2">
          <a href="cuenta.php" class="btn btn-al-sahara-oscuro px-4">Mi cuenta</a>
          <button type="button" id="btnSalir" class="btn btn-al-sahara-secundario px-4">Salir</button>
        </div>
      </div>
    </div>

  </div>
</header>

<script>
(function(){
  var nav = document.getElementById('alSaharaNavbar');
  if (nav) window.addEventListener('scroll', function(){
    nav.classList.toggle('al-sahara-navbar-scrolled', window.scrollY > 10);
  }, { passive: true });

  function actualizarCarrito(){
    var n = 0;
    try {
      var cart = JSON.parse(localStorage.getItem('alSaharaCart') || '{}');
      Object.keys(cart).forEach(function(k){ n += cart[k]; });
    } catch (e) {}
    var el = document.getElementById('cartCount');
    if (el) el.textContent = n;
  }
  actualizarCarrito();
  window.addEventListener('cart:changed', actualizarCarrito);
  window.addEventListener('storage', actualizarCarrito);

  // Sesión: el navegador no puede leer la cookie HttpOnly, así que pregunta al backend (S07)
  window.addEventListener('DOMContentLoaded', async function(){
    if (typeof api !== 'function') return;
    var ingresar = document.getElementById('btnIngresar');
    var box = document.getElementById('sesionBox');
    try {
      await api('/clients/me');
      ingresar.classList.add('d-none');
      box.classList.remove('d-none');
      box.classList.add('d-flex');
    } catch (e) { /* sin sesión o sin conexión: se mantiene "Ingresar" */ }
  });

  var salir = document.getElementById('btnSalir');
  if (salir) salir.addEventListener('click', async function(){
    try { await api('/auth/logout', { method: 'POST' }); } catch (e) {}   // S06
    location.href = '<?= $base ?: 'index.php' ?>';
  });
})();
</script>
