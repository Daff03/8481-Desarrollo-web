<section id="inicio" class="al-sahara-hero position-relative overflow-hidden">
  <div class="container px-4 px-lg-5">
    <div class="row align-items-center gy-5 gx-lg-5">

      <div class="col-lg-6 position-relative al-sahara-reveal">
        <div class="al-sahara-hero-img">
          <img src="assets/img/hero-restaurante.jpg" alt="Salón del restaurante Al Sahara con lámparas árabes, sillones y mesas puestas" width="1200" height="900" fetchpriority="high">
        </div>

        <div class="al-sahara-hero-badge d-flex flex-column align-items-center justify-content-center text-center">
          <span class="al-sahara-hero-badge-number" data-count="36">0</span>
          <span class="al-sahara-hero-badge-label">años de<br>tradición</span>
        </div>
      </div>

      <div class="col-lg-6">
        <p class="al-sahara-eyebrow al-sahara-reveal">— Desde el año 1990</p>

        <h1 class="al-sahara-hero-title al-sahara-reveal">
          Tradición familiar<br><em>desde Arabia Saudita</em>
        </h1>

        <p class="al-sahara-hero-subtitle al-sahara-reveal">
          Cocina tradicional árabe de alta calidad, preparada como en casa desde hace más de tres décadas.
        </p>

        <a href="#historia" class="al-sahara-hero-link al-sahara-reveal">
          Conoce más sobre nosotros <span class="al-sahara-hero-link-arrow">→</span>
        </a>

        <div class="row row-cols-2 g-4 al-sahara-reveal-stagger">
          <div class="col d-flex gap-3">
            <span class="al-sahara-feature-icon">🌿</span>
            <div>
              <strong class="d-block">Ingredientes importados</strong>
              <span class="small al-sahara-feature-text">Directos de Arabia</span>
            </div>
          </div>
          <div class="col d-flex gap-3">
            <span class="al-sahara-feature-icon">🍽️</span>
            <div>
              <strong class="d-block">Recetas típicas</strong>
              <span class="small al-sahara-feature-text">Desde 1990</span>
            </div>
          </div>
          <div class="col d-flex gap-3">
            <span class="al-sahara-feature-icon">🤝</span>
            <div>
              <strong class="d-block">Atención personalizada</strong>
              <span class="small al-sahara-feature-text">Trato cercano y familiar</span>
            </div>
          </div>
          <div class="col d-flex gap-3">
            <span class="al-sahara-feature-icon">❤</span>
            <div>
              <strong class="d-block">Ambiente familiar</strong>
              <span class="small al-sahara-feature-text">Como en casa</span>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</section>

<script>
(function(){
  var revealEls = document.querySelectorAll('#inicio .al-sahara-reveal, #inicio .al-sahara-reveal-stagger');
  var revealObserver = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if (entry.isIntersecting){
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.2 });
  revealEls.forEach(function(el){ revealObserver.observe(el); });

  var counterEl = document.querySelector('.al-sahara-hero-badge-number');
  if (!counterEl) return;
  var started = false;
  var counterObserver = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if (entry.isIntersecting && !started){
        started = true;
        var target = parseInt(counterEl.getAttribute('data-count'), 10);
        var start = null;
        var duration = 1400;
        function step(ts){
          if (!start) start = ts;
          var progress = Math.min((ts - start) / duration, 1);
          var eased = 1 - Math.pow(1 - progress, 3);
          counterEl.textContent = Math.floor(eased * target);
          if (progress < 1) requestAnimationFrame(step);
          else counterEl.textContent = target;
        }
        requestAnimationFrame(step);
        counterObserver.disconnect();
      }
    });
  }, { threshold: 0.5 });
  counterObserver.observe(counterEl);
})();
</script>
