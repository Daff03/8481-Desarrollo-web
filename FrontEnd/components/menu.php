<section id="menu" class="al-sahara-menu">
  <div class="container px-4 px-lg-5">

    <div class="text-center mb-5 al-sahara-reveal">
      <span class="al-sahara-eyebrow d-block">— Nuestra Carta —</span>
      <h2 class="al-sahara-menu-title">Menú del Restaurante</h2>
    </div>

    <ul class="nav justify-content-center gap-2 mb-5 al-sahara-menu-tabs al-sahara-reveal" id="menuTabs" role="tablist">
      <li class="nav-item">
        <button class="nav-link active al-sahara-tab-btn" data-category="entradas" role="tab" aria-selected="true">Entradas</button>
      </li>
      <li class="nav-item">
        <button class="nav-link al-sahara-tab-btn" data-category="carnes" role="tab" aria-selected="false">Carnes</button>
      </li>
      <li class="nav-item">
        <button class="nav-link al-sahara-tab-btn" data-category="vegetarianos" role="tab" aria-selected="false">Vegetarianos</button>
      </li>
      <li class="nav-item">
        <button class="nav-link al-sahara-tab-btn" data-category="postres" role="tab" aria-selected="false">Postres</button>
      </li>
    </ul>

    <div class="row row-cols-1 row-cols-md-3 g-4" id="menuGrid">

      <!-- Entradas -->
      <div class="col al-sahara-dish" data-category="entradas">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="badge al-sahara-dish-tag">Popular</span>
            <span class="al-sahara-dish-emoji">🧆</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Hummus Tradicional</h5>
            <p class="card-text small al-sahara-dish-desc">Puré de garbanzos con tahini, aceite de oliva y especias árabes, servido con pan pita tibio.</p>
            <span class="al-sahara-dish-price">$6.990 CLP</span>
          </div>
        </div>
      </div>

      <div class="col al-sahara-dish" data-category="entradas">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="badge al-sahara-dish-tag">Popular</span>
            <span class="al-sahara-dish-emoji">🍆</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Baba Ganoush</h5>
            <p class="card-text small al-sahara-dish-desc">Berenjena ahumada al fuego, mezclada con ajo, limón y tahini.</p>
            <span class="al-sahara-dish-price">$7.490 CLP</span>
          </div>
        </div>
      </div>

      <div class="col al-sahara-dish" data-category="entradas">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="al-sahara-dish-emoji">🥟</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Fatayer de Espinaca</h5>
            <p class="card-text small al-sahara-dish-desc">Empanadillas árabes horneadas, rellenas de espinaca, cebolla y especias.</p>
            <span class="al-sahara-dish-price">$5.990 CLP</span>
          </div>
        </div>
      </div>

      <!-- Carnes -->
      <div class="col al-sahara-dish d-none" data-category="carnes">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="badge al-sahara-dish-tag">Popular</span>
            <span class="al-sahara-dish-emoji">🍢</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Shawarma de Cordero</h5>
            <p class="card-text small al-sahara-dish-desc">Cordero marinado 24 horas en especias árabes, servido con arroz y salsa de ajo.</p>
            <span class="al-sahara-dish-price">$12.990 CLP</span>
          </div>
        </div>
      </div>

      <div class="col al-sahara-dish d-none" data-category="carnes">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="al-sahara-dish-emoji">🍖</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Kebab Mixto</h5>
            <p class="card-text small al-sahara-dish-desc">Brochetas de cordero y pollo a la parrilla, acompañadas de arroz árabe.</p>
            <span class="al-sahara-dish-price">$13.990 CLP</span>
          </div>
        </div>
      </div>

      <div class="col al-sahara-dish d-none" data-category="carnes">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="al-sahara-dish-emoji">🥘</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Kafta Al Sahara</h5>
            <p class="card-text small al-sahara-dish-desc">Carne molida especiada a la parrilla, bañada en salsa de tahini.</p>
            <span class="al-sahara-dish-price">$11.990 CLP</span>
          </div>
        </div>
      </div>

      <!-- Vegetarianos -->
      <div class="col al-sahara-dish d-none" data-category="vegetarianos">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="badge al-sahara-dish-tag">Popular</span>
            <span class="al-sahara-dish-emoji">🧆</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Falafel Casero</h5>
            <p class="card-text small al-sahara-dish-desc">Croquetas de garbanzo y hierbas frescas, fritas al momento, con salsa de yogur.</p>
            <span class="al-sahara-dish-price">$8.990 CLP</span>
          </div>
        </div>
      </div>

      <div class="col al-sahara-dish d-none" data-category="vegetarianos">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="al-sahara-dish-emoji">🥗</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Tabbouleh</h5>
            <p class="card-text small al-sahara-dish-desc">Ensalada de perejil fresco, trigo bulgur, tomate y limón.</p>
            <span class="al-sahara-dish-price">$6.490 CLP</span>
          </div>
        </div>
      </div>

      <div class="col al-sahara-dish d-none" data-category="vegetarianos">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="al-sahara-dish-emoji">🫓</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Fatteh de Garbanzos</h5>
            <p class="card-text small al-sahara-dish-desc">Pan pita crocante con garbanzos, yogur y un toque de granada.</p>
            <span class="al-sahara-dish-price">$8.490 CLP</span>
          </div>
        </div>
      </div>

      <!-- Postres -->
      <div class="col al-sahara-dish d-none" data-category="postres">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="badge al-sahara-dish-tag">Popular</span>
            <span class="al-sahara-dish-emoji">🍯</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Baklava</h5>
            <p class="card-text small al-sahara-dish-desc">Hojaldre crujiente relleno de nueces, bañado en miel de rosas.</p>
            <span class="al-sahara-dish-price">$4.990 CLP</span>
          </div>
        </div>
      </div>

      <div class="col al-sahara-dish d-none" data-category="postres">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="al-sahara-dish-emoji">🍮</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Kunafa</h5>
            <p class="card-text small al-sahara-dish-desc">Queso dulce cubierto con fideos crujientes, bañado en almíbar.</p>
            <span class="al-sahara-dish-price">$5.990 CLP</span>
          </div>
        </div>
      </div>

      <div class="col al-sahara-dish d-none" data-category="postres">
        <div class="card h-100 border-0 al-sahara-dish-card">
          <div class="al-sahara-dish-img">
            <span class="al-sahara-dish-emoji">🍚</span>
          </div>
          <div class="card-body">
            <h5 class="card-title al-sahara-dish-name">Muhallabia</h5>
            <p class="card-text small al-sahara-dish-desc">Pudín de leche con agua de rosas, decorado con pistachos.</p>
            <span class="al-sahara-dish-price">$4.490 CLP</span>
          </div>
        </div>
      </div>

    </div>
  </div>
</section>
