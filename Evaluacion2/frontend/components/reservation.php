<section id="contacto" class="py-5" style="background-color: var(--color-secundario);">
  <div class="container">
    <div class="row g-5">

      <div class="col-lg-6">
        <h3 class="mb-4">Datos de la reserva</h3>

        <div class="alert alert-success d-none" id="alerta-exito">Reserva realizada con éxito.</div>
        <div class="alert alert-danger d-none" id="alerta-error">Hubo un problema. Intenta nuevamente.</div>

        <form id="form-reserva" novalidate>
          <div class="row g-3">
            <div class="col-md-8">
              <label class="form-label">Nombre completo</label>
              <input type="text" class="form-control input-al-sahara" name="nombre" required>
            </div>
            <div class="col-md-4">
              <label class="form-label">N° de personas</label>
              <select class="form-select input-al-sahara" name="personas">
                <option value="1">1 persona</option>
                <option value="2" selected>2 personas</option>
                <option value="3">3 personas</option>
                <option value="4">4 personas</option>
                <option value="5">5 personas</option>
                <option value="6">6 personas</option>
                <option value="7">7 personas</option>
                <option value="8">8 personas</option>
                <option value="9+">9 o más personas</option>
              </select>
            </div>
            <div class="col-12">
              <label class="form-label">Correo electrónico</label>
              <input type="email" class="form-control input-al-sahara" name="email" required>
            </div>
            <div class="col-12">
              <label class="form-label">Fecha y hora</label>
              <input type="datetime-local" class="form-control input-al-sahara" name="fecha" required>
            </div>
            <div class="col-12">
              <label class="form-label">Mensaje opcional</label>
              <textarea class="form-control input-al-sahara" name="mensaje" rows="3"></textarea>
            </div>
            <div class="col-12">
              <button type="submit" class="btn btn-al-sahara-primario w-100 py-2">Reservar Ahora</button>
            </div>
          </div>
        </form>
      </div>

      <div class="col-lg-6">
        <h3 class="mb-3">Reserve su mesa hoy</h3>
        <p class="text-muted">
          Viva una experiencia gastronómica completa. Nuestro equipo lo recibirá
          con una calidad y hospitalidad árabe que nos caracteriza.
        </p>

        <ul class="list-unstyled mt-4">
          <li class="mb-3">📍 <strong>Dirección</strong><br><span class="text-muted">Por definir</span></li>
          <li class="mb-3">☎ <strong>Número telefónico</strong><br><span class="text-muted">Por definir</span></li>
          <li class="mb-3">🕐 <strong>Horario disponible</strong><br><span class="text-muted">Por definir</span></li>
        </ul>
      </div>

    </div>
  </div>
</section>