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
