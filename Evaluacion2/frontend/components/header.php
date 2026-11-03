<header class="navbar navbar-expand-lg fixed-top py-3" id="alSaharaNavbar">
  <div class="container">

    <a class="navbar-brand d-flex align-items-center gap-2" href="#inicio">
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
        <li class="nav-item"><a class="nav-link" href="#inicio">Inicio</a></li>
        <li class="nav-item"><a class="nav-link" href="#menu">Menú</a></li>
        <li class="nav-item"><a class="nav-link" href="#historia">Nuestra Historia</a></li>
        <li class="nav-item"><a class="nav-link" href="#contacto">Contacto</a></li>
      </ul>
      <a href="#contacto" class="btn btn-al-sahara-secundario px-4 align-self-center align-self-lg-auto">Reservar Mesa</a>
    </div>

  </div>
</header>

<script>
(function(){
  var nav = document.getElementById('alSaharaNavbar');
  if (!nav) return;
  window.addEventListener('scroll', function(){
    nav.classList.toggle('al-sahara-navbar-scrolled', window.scrollY > 10);
  }, { passive: true });
})();
</script>
