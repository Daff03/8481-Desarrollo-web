// ---------- Carrito (solo ids y cantidades; el servidor calcula precios y totales) ----------
// Va primero y en su propio bloque: si falla otra parte de este archivo, el carrito igual funciona.
(function () {
  var KEY = 'alSaharaCart';

  function leer() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { return {}; }
  }

  function actualizarContador() {
    var n = 0, c = leer();
    Object.keys(c).forEach(function (k) { n += c[k]; });
    var el = document.getElementById('cartCount');
    if (el) el.textContent = n;
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest('.al-sahara-add');
    if (!b) return;
    var cart = leer();
    cart[b.dataset.id] = Math.min((cart[b.dataset.id] || 0) + 1, 20);
    try {
      localStorage.setItem(KEY, JSON.stringify(cart));
    } catch (err) {
      console.error('No se pudo guardar el carrito:', err);
      return;
    }
    actualizarContador();
    window.dispatchEvent(new Event('cart:changed'));
    b.textContent = 'Agregado ✓';
    setTimeout(function () { b.textContent = 'Agregar'; }, 1200);
  });

  actualizarContador();
})();

// ---------- Menú: pestañas y animaciones ----------
(function () {
  var tabs = document.querySelectorAll('.al-sahara-tab-btn');
  var dishes = document.querySelectorAll('.al-sahara-dish');

  function showCategory(category) {
    dishes.forEach(function (dish) {
      dish.classList.toggle('d-none', dish.getAttribute('data-category') !== category);
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (t) {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      showCategory(tab.getAttribute('data-category'));
    });
  });

  var revealEls = document.querySelectorAll('#menu .al-sahara-reveal, .al-sahara-dish');
  var revealObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });
  revealEls.forEach(function (el) { revealObserver.observe(el); });
})();
