<?php $titulo = 'Pago del pedido'; $base = 'index.php'; include 'components/head.php'; ?>
<main class="al-sahara-page">
  <div class="container" style="max-width: 720px;">
    <div class="al-sahara-card">
      <h1 class="mb-1">Pago del pedido</h1>
      <p class="text-muted">El pago se confirma en la pasarela del proveedor; esta página solo muestra el resultado.</p>
      <div id="alerta" role="alert"></div>
      <div id="resumen"></div>
      <div class="d-flex justify-content-between align-items-center mt-3">
        <div>Total: <span class="al-sahara-total" id="total">$0</span></div>
        <button class="btn btn-al-sahara-primario px-4 py-2 d-none" type="button" id="btn-pagar">Pagar ahora</button>
      </div>
      <p class="small mt-3 mb-0 d-none" id="boleta"></p>
    </div>
  </div>
</main>
<?php include 'components/foot.php'; ?>
<script src="js/pago.js"></script>
</body></html>
