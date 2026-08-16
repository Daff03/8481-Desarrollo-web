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
    <div class="container-fluid">
      <div class="row">
        <div class="col-12">
          <h1>Productos</h1>
          <p>Esta es la página de productos.</p>
        </div>

        <!-- Fila de Zapatillas -->
        <div class="row mt-4">
            <div class="col-12">
                <h2>Zapatillas</h2>
            </div>

            <div class="col-md-4">
                <div class="card" style="width:400px">
                    <img class="card-img-top" src="Zapatilla_1.png" alt="Card image" style="width:100%">
                    <div class="card-body">
                        <h4 class="card-title">Jordan Son of Mars Low</h4>
                        <p class="card-text">El Jordan Son of Mars Low juega con estilo en un diseño que rinde homenaje a la combinación de Mike, Spike y la legendaria campaña publicitaria que los unió. La combinación de cuero auténtico y sintético brinda comodidad y durabilidad, mientras que los detalles clásicos de Jordan lo convierten en una leyenda.</p>
                        <a href="#" class="btn btn-primary">Ver Producto</a>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card" style="width:400px">
                    <img class="card-img-top" src="Zapatilla_2.png" alt="Card image" style="width:100%">
                    <div class="card-body">
                        <h4 class="card-title">Nike Air Max 90 Premium</h4>
                        <p class="card-text">El Air Max 90 se mantiene fiel a sus raíces de running con la icónica suela Waffle, mientras que las superposiciones cosidas y los detalles texturizados crean el look de los 90 que tanto te gusta. Con colores fáciles de combinar, su amortiguación visible agrega comodidad a cada paso.</p>
                        <a href="#" class="btn btn-primary">Ver Producto</a>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card" style="width:400px">
                    <img class="card-img-top" src="Zapatilla_3.png" alt="Card image" style="width:100%" ">
                    <div class="card-body">
                        <h4 class="card-title">Nike Revolution 8</h4>
                        <p class="card-text">Los Revolution 8 son la evolución de tu modelo favorito. La entresuela de espuma y el antepié flexible ofrecen amortiguación, lo que brinda suavidad en cada pisada. Además, la capellada de malla es aún más transpirable que la versión anterior para que puedas correr con mayor frescura y comodidad.</p>
                        <a href="#" class="btn btn-primary">Ver Producto</a>
                    </div>
                </div>
            </div>
        </div>

        <!-- Fila de Poleras -->
        <div class="row mt-4 mb-5">
            <div class="col-12">
                <h2>Poleras</h2>
            </div>

            <div class="col-md-4">
                <div class="card">
                    <img class="card-img-top" src="Polera_1.png" alt="Polera 1" style="height:500px">
                    <div class="card-body">
                        <h4 class="card-title">NIKE ESSENTIAL</h4>
                        <p class="card-text">Atrae miradas, no rayos. Con tecnología Dri-FIT y protección UPF 40, esta camiseta de estilo deportivo te mantendrá seco, cómodo y protegido para que puedas jugar o relajarte todo el día. Con una amplia variedad de colores, seguro encontrarás uno que represente a tu equipo o se ajuste a tu estado de ánimo.</p>
                        <a href="#" class="btn btn-primary">Ver Producto</a>
                    </div>
                </div>    
            </div>
        
            <div class="col-md-4">
                <div class="card">
                    <img class="card-img-top" src="Polera_2.png" alt="Polera 2" style="height:500px">
                    <div class="card-body">
                        <h4 class="card-title">Nike Swift</h4>
                        <p class="card-text">Utilizamos información de runners como tú para priorizar la funcionalidad y actualizar nuestras prendas básicas Swift. Esta polera ligera se ha diseñado para ayudar a reducir el roce y mejorar la transpirabilidad. Es suave y absorbe el sudor para que puedas concentrarte en los kilómetros que tienes por delante.</p>
                        <a href="#" class="btn btn-primary">Ver Producto</a>
                    </div>
                </div>    
            </div>

            <div class="col-md-4">
                <div class="card">
                    <img class="card-img-top" src="Polera_3.png" alt="Polera 3" style="height:500px">
                    <div class="card-body">
                        <h4 class="card-title">Nike Tech</h4>
                        <p class="card-text">Nike Tech es más que solo polar: es una cultura. Navegar la ciudad es un deporte en sí mismo y esta polera fue hecha para jugar. Un fit moderno y una capa de malla crean un look inspirado en las calles. Más detalles. La tecnología Nike Dri-FIT ADV combina tela que absorbe la humedad con ingeniería avanzada y características que te ayudan a mantenerte seco y cómodo. Corte holgado y liviano para mayor libertad de movimiento en la ciudad.</p>
                        <a href="#" class="btn btn-primary">Ver Producto</a>
                    </div>
                </div>    
            </div>
        </div>
    </div>

    <!-- Footer -->
    <div class="container-fluid mt-5 bg-dark text-white ">
      <div class="row">
        <div class="col-4"></div>
            </div>
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
          <form action="/action_page.php">
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