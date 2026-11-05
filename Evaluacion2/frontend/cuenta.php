<?php $titulo = 'Mi cuenta'; $base = 'index.php'; include 'components/head.php'; ?>
<main class="al-sahara-page">
  <div class="container" style="max-width: 920px;">

    <h1 class="mb-1">Mi cuenta</h1>
    <p class="text-muted">Tu perfil, tus direcciones y tus pedidos.</p>
    <div id="alerta" role="alert"></div>

    <!-- Perfil (S07 / S08) -->
    <section class="al-sahara-card mb-4">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h2 class="h4 mb-0">Datos personales</h2>
        <button type="button" id="btn-editar-perfil" class="btn btn-al-sahara-secundario btn-sm px-3">Editar</button>
      </div>
      <form id="form-perfil" class="row g-3">
        <div class="col-md-6">
          <label class="form-label">RUN</label>
          <input class="form-control" id="pf-run" disabled>
          <div class="form-text">El RUN no se puede cambiar.</div>
        </div>
        <div class="col-md-6">
          <label class="form-label">Correo</label>
          <input class="form-control" id="pf-email" disabled>
        </div>
        <div class="col-md-6">
          <label class="form-label" for="pf-nombre">Nombre y apellido</label>
          <input class="form-control" id="pf-nombre" name="nombre" disabled required minlength="3" maxlength="80">
        </div>
        <div class="col-md-3">
          <label class="form-label" for="pf-sexo">Sexo</label>
          <select class="form-select" id="pf-sexo" name="sexo" disabled>
            <option value="F">Femenino</option>
            <option value="M">Masculino</option>
            <option value="O">Otro</option>
          </select>
        </div>
        <div class="col-md-3">
          <label class="form-label" for="pf-telefono">Teléfono</label>
          <input class="form-control" id="pf-telefono" name="telefono" disabled required>
        </div>
        <div class="col-12 d-none" id="perfil-acciones">
          <button type="submit" class="btn btn-al-sahara-primario px-4">Guardar</button>
          <button type="button" id="btn-cancelar-perfil" class="btn btn-al-sahara-oscuro px-4">Cancelar</button>
        </div>
      </form>
    </section>

    <!-- Direcciones (S36–S39) -->
    <section class="al-sahara-card mb-4">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h2 class="h4 mb-0">Mis direcciones <span class="text-muted small" id="dir-contador"></span></h2>
        <button type="button" id="btn-nueva-dir" class="btn btn-al-sahara-secundario btn-sm px-3">Agregar</button>
      </div>
      <div id="direcciones"><p class="text-muted mb-0">Cargando…</p></div>

      <form id="form-dir" class="row g-3 mt-2 d-none border-top pt-3">
        <h3 class="h6">Nueva dirección</h3>
        <div class="col-md-4">
          <label class="form-label" for="d-alias">Alias</label>
          <input class="form-control" id="d-alias" maxlength="30" placeholder="Casa, Trabajo…">
        </div>
        <div class="col-md-8">
          <label class="form-label" for="d-direccion">Dirección</label>
          <input class="form-control" id="d-direccion" required minlength="5" maxlength="120">
        </div>
        <div class="col-md-4">
          <label class="form-label" for="d-comuna">Comuna</label>
          <input class="form-control" id="d-comuna" required minlength="2" maxlength="60">
        </div>
        <div class="col-md-4">
          <label class="form-label" for="d-provincia">Provincia</label>
          <input class="form-control" id="d-provincia" required minlength="2" maxlength="60">
        </div>
        <div class="col-md-4">
          <label class="form-label" for="d-region">Región</label>
          <input class="form-control" id="d-region" required minlength="2" maxlength="60">
        </div>
        <div class="col-12 form-check ms-2">
          <input class="form-check-input" type="checkbox" id="d-principal">
          <label class="form-check-label" for="d-principal">Usar como dirección principal</label>
        </div>
        <div class="col-12">
          <button type="submit" class="btn btn-al-sahara-primario px-4">Guardar dirección</button>
          <button type="button" id="btn-cancelar-dir" class="btn btn-al-sahara-oscuro px-4">Cancelar</button>
        </div>
      </form>
    </section>

    <!-- Pedidos (GraphQL: misPedidos; anulación: anularPedido) -->
    <section class="al-sahara-card">
      <h2 class="h4 mb-3">Mis pedidos</h2>
      <div id="pedidos"><p class="text-muted mb-0">Cargando…</p></div>
    </section>

  </div>
</main>
<?php include 'components/foot.php'; ?>
<script src="js/cuenta.js"></script>
</body></html>
