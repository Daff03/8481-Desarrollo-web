<!DOCTYPE html>
<html lang="en">
  <head>

    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-EVSTQN3/azprG1Anm3QDgpJLIm9Nao0Yz1ztcQTwFspd3yD65VohhpuuCOmLASjC" crossorigin="anonymous">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
    <title>Pagina Empresa</title>

  </head>

  <body>
    <!-- Navbar -->
    <nav class="navbar navbar-expand-sm bg-light navbar-light">
      <div class="container-fluid">
        <a class="navbar-brand" href="index.php"><!-- Texto en lugar de imagen -->
          <img src="Logo_NIIKE.PNG" alt="" width="40" height="24" class="d-inline-block align-text-top"> 
        </a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="collapsibleNavbar">
          <ul class="navbar-nav me-auto">
            <li class="nav-item dropdown">
              <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Dropdown</a>
              <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="servicios.php">Servicios</a></li>
                <li><a class="dropdown-item" href="productos.php">Productos</a></li>
                <li><a class="dropdown-item" href="politica.php">Política de Privacidad</a></li>
              </ul>
            </li>
            <li class="nav-item">
              <a class="nav-link" href="index.php">Principal</a>
            </li>
            <li class="nav-item">
              <a class="nav-link" href="empresa.php">Empresa</a>
            </li>
            <li class="nav-item">
              <a class="nav-link" href="contacto.php">Contacto</a>
            </li>
            <li class="nav-item">
              
            </li>
          </ul>
          <button type="button" class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#inicioSesion">Iniciar Sesión</button>
        </div>
      </div>
    </nav>

    <!-- Container -->
    <div class="container-fluid bg-light py-5">
      <h1 class="display-4 fw-bold text-center">Nuestra Empresa</h1>
      <p class="lead text-center">Conoce más sobre nuestra historia, misión y visión</p>
      <div class="row mt-5">
        <div class="col-md-6">
          <h3>Misión</h3>
          <p>Nuestra misión es ofrecer productos de alta calidad que satisfagan las necesidades de nuestros clientes, brindando un excelente servicio y fomentando la innovación en cada uno de nuestros procesos.</p>
        </div>
        <div class="col-md-6">
          <h3>Visión</h3>
          <p>Nuestra visión es ser líderes en el mercado, reconocidos por nuestra excelencia en productos y servicios, y por nuestro compromiso con la sostenibilidad y la responsabilidad social.</p>
        </div>
      </div>
    </div>



    <!-- Footer -->
    <div class="container-fluid mt-5 bg-dark text-white ">
      <div class="row">
        <div class="col-6 col-sm-3 d-flex flex-column align-items-center text-center mb-1 ">
          <img src="Logo_NIIKE.PNG" alt="" width="40" height="24" class="d-inline-block align-text-top"> 
          <p class="mt-2 small">Ofrecemos zapatos y poleras de gran calidad para uso casual, amantes de la moda y deportistas</p>
        </div>
        <div class="col-6 col-sm-3  d-flex flex-column align-items-center text-center mb-1 ">
          <h5>Enlaces</h5>
          <ul class="list-unstyled">
            <li><br><a href="empresa.php" class="text-white">Empresa</a></li>
            <li><a href="contacto.php" class="text-white">Contacto</a></li>
            <li><a href="servicios.php" class="text-white">Servicios</a></li>
            <li><a href="productos.php" class="text-white">Productos</a></li>
          </ul>
        </div>
        <div class="col-6 col-sm-3  d-flex flex-column align-items-center text-center mb-1 ">
          <h5>Legal</h5>
          <ul class="list-unstyled">
            <li><br></li>
            <li><a href="politica.php" class="text-white">Política de Privacidad</a></li>
          </ul>
        </div>
        <div class="col-6 col-sm-3  d-flex flex-column align-items-center text-center mb-1 ">
          <h5>Contacto</h5>
          <ul class="list-unstyled">
            <li><i class="fa fa-envelope"></i> info@niike.com</li>
            <li><i class="fa fa-phone"></i> +1 234 567 890</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <div class="modal fade" id="inicioSesion">
      <div class="modal-dialog">
        <div class="modal-content">

          <!-- Modal Header -->
          <div class="modal-header">
            <h4 class="modal-title">Iniciar Sesión</h4>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>

          <!-- Modal body -->
          <form action="productos.php">
            <div class="m-3">
              <label for="email" class="form-label">ID de Usuario:</label>
              <input type="email" class="form-control" id="email" placeholder="" name="email">
            </div>
            <div class="mb-3 mx-3">
              <label for="pwd" class="form-label">Contraseña:</label>
              <input type="password" class="form-control" id="pwd" placeholder="" name="pswd">
            </div>
            <div class="form-check mb-3 mx-3">
              <label class="form-check-label">
                <input class="form-check-input" type="checkbox" name="remember"> Recordar credenciales
              </label>
            </div>
            <button type="submit" class="btn btn-primary mx-3 mb-3">Iniciar Sesión <i class="fa fa-check-circle "></i></button>
          </form>

          <!-- Modal footer -->
          <div class="modal-footer">
            <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Cerrar <i class="fa fa-remove "></i></button>
          </div>

        </div>
      </div>
    </div>


    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js" integrity="sha384-MrcW6ZMFYlzcLA8Nl+NtUVF0sA7MsXsP1UyJoMp4YLEuNSfAP+JcXn/tWtIaxVXM" crossorigin="anonymous"></script>
  </body>
</html>