const btnLogin = document.querySelector('#inicioSesion button[type="submit"]');

let texto = document.createElement("input");
texto.setAttribute("type", "password");
texto.setAttribute("placeholder", "Confirma tu contraseña");
texto.className = "form-control mb-2 mx-2"; 
btnLogin.insertAdjacentElement("beforebegin", texto);

let responseAPI = {
  "data": [
    {"id":"1","nombre":"Región de Arica y Parinacota"},
    {"id":"2","nombre":"Región de Tarapacá"},
    {"id":"3","nombre":"Región de Antofagasta"},
    {"id":"4","nombre":"Región de Atacama"},
    {"id":"5","nombre":"Región de Coquimbo"},
    {"id":"6","nombre":"Región de Valparaíso"},
    {"id":"7","nombre":"Región Metropolitana de Santiago"},
    {"id":"8","nombre":"Región del Libertador General Bernardo O'Higgins"},
    {"id":"9","nombre":"Región del Maule"},
    {"id":"10","nombre":"Región de Ñuble"},
    {"id":"11","nombre":"Región del Biobío"},
    {"id":"12","nombre":"Región de La Araucanía"},
    {"id":"13","nombre":"Región de Los Ríos"},
    {"id":"14","nombre":"Región de Los Lagos"},
    {"id":"15","nombre":"Región Aysén del General Carlos Ibáñez del Campo"},
    {"id":"16","nombre":"Región de Magallanes y de la Antártica Chilena"}
  ]
};

let cmbRegion = document.createElement("select");
cmbRegion.setAttribute("name", "cmbRegion");

let optionDefault = document.createElement("option");
optionDefault.setAttribute("value", "");
optionDefault.innerText = "Ingrese su región de estadía";
optionDefault.setAttribute("disabled", "");
optionDefault.setAttribute("selected", "");
cmbRegion.appendChild(optionDefault);

responseAPI.data.forEach((reg) => {
let optionAux = document.createElement("option");
  optionAux.setAttribute("value", reg.id);
  optionAux.innerText = reg.nombre;
  cmbRegion.appendChild(optionAux);
});
cmbRegion.className = "form-control mb-2 mx-2"; 

btnLogin.insertAdjacentElement("beforebegin", cmbRegion);