<?php $titulo = 'Tu pedido'; $base = 'index.php'; include 'components/head.php'; ?>
<main class="al-sahara-page">
  <div class="container" style="max-width: 820px;">
    <div class="al-sahara-card">
      <h1 class="mb-1">Tu pedido</h1>
      <p class="text-muted">Entrega gratis dentro de 3 km del local.</p>
      <div id="alerta" role="alert"></div>
      <div id="carrito"></div>
      <div id="vacio" class="text-center py-4 d-none">Tu carrito está vacío. <a href="index.php#menu">Elige platos del menú</a>.</div>

      <form id="form-pedido" class="mt-4 d-none" novalidate>
        <div class="row g-3">
          <div class="col-md-8"><label class="form-label" for="direccion">Dirección de entrega</label>
            <input class="form-control input-al-sahara" id="direccion" required>
            <div class="invalid-feedback">Ingresa la dirección de entrega.</div></div>
          <div class="col-md-4"><label class="form-label" for="comuna">Comuna</label>
            <input class="form-control input-al-sahara" id="comuna" required>
            <div class="invalid-feedback">Ingresa la comuna.</div></div>
          <div class="col-12"><label class="form-label" for="comentario">Comentario (opcional)</label>
            <textarea class="form-control input-al-sahara" id="comentario" rows="2" maxlength="200"></textarea></div>
          <div class="col-12 d-flex justify-content-between align-items-center">
            <div>Total estimado: <span class="al-sahara-total" id="total">$0</span>
              <div class="small text-muted">El total final lo confirma el restaurante.</div></div>
            <button class="btn btn-al-sahara-primario px-4 py-2" type="submit" id="btn-pedido">Confirmar pedido</button>
          </div>
        </div>
      </form>
    </div>
  </div>
</main>
<?php include 'components/foot.php'; ?>
<script src="js/pedido.js"></script>
</body></html>
