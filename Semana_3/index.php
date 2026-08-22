<!DOCTYPE html>
<html lang="en">
  <head>

    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-EVSTQN3/azprG1Anm3QDgpJLIm9Nao0Yz1ztcQTwFspd3yD65VohhpuuCOmLASjC" crossorigin="anonymous">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
    <title>NIIKE</title>

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
    <div class="container-fluid bg-dark text-white text-center py-5">
      <h1 class="display-4 fw-bold">Estilo y rendimiento en cada paso</h1>
      <p class="lead">Zapatos y poleras de gran calidad para moda y deporte</p>
      <a href="productos.php" class="btn btn-light btn-lg mt-3">Ver Productos</a>
    </div>
    <!-- Carousel -->
    <div id="demo" class="carousel slide" data-bs-ride="carousel">

      <!-- Indicators/dots -->
      <div class="carousel-indicators">
        <button type="button" data-bs-target="#demo" data-bs-slide-to="0" class="active"></button>
        <button type="button" data-bs-target="#demo" data-bs-slide-to="1"></button>
        <button type="button" data-bs-target="#demo" data-bs-slide-to="2"></button>
      </div>

      <!-- The slideshow/carousel -->
      <div class="carousel-inner">
        <div class="carousel-item active">
          <img src="imagen_1.png" alt="Air Jordan 1 Retro High OG" class="d-block mx-auto " style=" 100%; height: 500px;">
        </div>
          <div class="carousel-item">
          <img src="imagen_2.png" alt="Jordan 1 Patent Bred" class="d-block mx-auto " style="100%; height: 500px;">
        </div>
        <div class="carousel-item">
          <img src="imagen_3.png" alt="Niike Revolution 8" class="d-block mx-auto " style=" 100%; height: 500px;">
        </div>
      </div>

      <!-- Left and right controls/icons -->
      <button class="carousel-control-prev" type="button" data-bs-target="#demo" data-bs-slide="prev">
        <span class="carousel-control-prev-icon"></span>
      </button>
      <button class="carousel-control-next" type="button" data-bs-target="#demo" data-bs-slide="next">
        <span class="carousel-control-next-icon"></span>
      </button>
    </div>

    <div class="container my-5 text-center">
      <h2> Sobre NIIKE</h2>
      <p class="col-md-8 mx-auto">
        En NIIKE Ofrecemos zapatos y poleras de grancalidad para uso casual, amantes de la moda y deportistas. Nuestra misión es brindar productos que combinen estilo y rendimiento, asegurando la satisfacción de nuestros clientes en cada paso que den.
      </p>
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