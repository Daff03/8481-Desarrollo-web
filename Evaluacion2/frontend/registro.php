<?php $titulo = 'Crear cuenta'; $base = 'index.php'; include 'components/head.php'; ?>
<main class="al-sahara-page">
  <div class="container" style="max-width: 760px;">
    <div class="al-sahara-card">
      <h1 class="mb-1">Crear cuenta</h1>
      <p class="text-muted">Regístrate para pedir online y acceder a promociones.</p>
      <div id="alerta" role="alert"></div>

      <form id="form-registro" novalidate>
        <div class="row g-3">
          <div class="col-md-4"><label class="form-label" for="run">RUN</label>
            <input class="form-control input-al-sahara" id="run" name="run" placeholder="12345678-5" required>
            <div class="invalid-feedback">Ingresa un RUN válido, por ejemplo 12345678-5.</div></div>
          <div class="col-md-8"><label class="form-label" for="nombre">Nombre completo</label>
            <input class="form-control input-al-sahara" id="nombre" name="nombre" autocomplete="name" required>
            <div class="invalid-feedback">Ingresa tu nombre completo.</div></div>
          <div class="col-12"><label class="form-label" for="direccion">Dirección</label>
            <input class="form-control input-al-sahara" id="direccion" name="direccion" autocomplete="street-address" required>
            <div class="invalid-feedback">Ingresa tu dirección.</div></div>
          <div class="col-md-4"><label class="form-label" for="comuna">Comuna</label>
            <input class="form-control input-al-sahara" id="comuna" name="comuna" required>
            <div class="invalid-feedback">Ingresa tu comuna.</div></div>
          <div class="col-md-4"><label class="form-label" for="provincia">Provincia</label>
            <input class="form-control input-al-sahara" id="provincia" name="provincia" required>
            <div class="invalid-feedback">Ingresa tu provincia.</div></div>
          <div class="col-md-4"><label class="form-label" for="region">Región</label>
            <input class="form-control input-al-sahara" id="region" name="region" required>
            <div class="invalid-feedback">Ingresa tu región.</div></div>
          <div class="col-md-4"><label class="form-label" for="fechaNacimiento">Fecha de nacimiento</label>
            <input type="date" class="form-control input-al-sahara" id="fechaNacimiento" name="fechaNacimiento" required>
            <div class="invalid-feedback">Debes ser mayor de 18 años.</div></div>
          <div class="col-md-4"><label class="form-label" for="sexo">Sexo</label>
            <select class="form-select input-al-sahara" id="sexo" name="sexo" required>
              <option value="">Selecciona</option><option value="F">Femenino</option>
              <option value="M">Masculino</option><option value="O">Otro</option></select>
            <div class="invalid-feedback">Selecciona una opción.</div></div>
          <div class="col-md-4"><label class="form-label" for="telefono">Teléfono</label>
            <input type="tel" class="form-control input-al-sahara" id="telefono" name="telefono" placeholder="+56912345678" required>
            <div class="invalid-feedback">Ingresa un teléfono válido.</div></div>
          <div class="col-md-6"><label class="form-label" for="email">Correo electrónico</label>
            <input type="email" class="form-control input-al-sahara" id="email" name="email" autocomplete="email" required>
            <div class="invalid-feedback">Ingresa un correo válido.</div></div>
          <div class="col-md-6"><label class="form-label" for="password">Contraseña</label>
            <input type="password" class="form-control input-al-sahara" id="password" name="password" minlength="8" autocomplete="new-password" required>
            <div class="invalid-feedback">Mínimo 8 caracteres, con letras y números.</div></div>
          <div class="col-12"><button class="btn btn-al-sahara-primario w-100 py-2" type="submit" id="btn-registro">Crear cuenta</button></div>
          <div class="col-12 text-center small">¿Ya tienes cuenta? <a href="login.php">Inicia sesión</a></div>
        </div>
      </form>
    </div>
  </div>
</main>
<?php include 'components/foot.php'; ?>
<script src="js/registro.js"></script>
</body></html>
