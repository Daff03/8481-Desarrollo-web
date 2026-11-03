<?php $titulo = 'Iniciar sesión'; $base = 'index.php'; include 'components/head.php'; ?>
<main class="al-sahara-page">
  <div class="container" style="max-width: 440px;">
    <div class="al-sahara-card">
      <h1 class="mb-3">Iniciar sesión</h1>
      <div id="alerta" role="alert"></div>
      <form id="form-login" novalidate>
        <div class="mb-3"><label class="form-label" for="email">Correo electrónico</label>
          <input type="email" class="form-control input-al-sahara" id="email" name="email" autocomplete="email" required>
          <div class="invalid-feedback">Ingresa un correo válido.</div></div>
        <div class="mb-3"><label class="form-label" for="password">Contraseña</label>
          <input type="password" class="form-control input-al-sahara" id="password" name="password" autocomplete="current-password" required>
          <div class="invalid-feedback">Ingresa tu contraseña.</div></div>
        <button class="btn btn-al-sahara-primario w-100 py-2" type="submit" id="btn-login">Entrar</button>
      </form>
      <p class="text-center small mt-3 mb-0">¿No tienes cuenta? <a href="registro.php">Crear cuenta</a></p>
    </div>
  </div>
</main>
<?php include 'components/foot.php'; ?>
<script src="js/login.js"></script>
</body></html>
