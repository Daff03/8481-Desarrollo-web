const btnEnviarContacto = document.querySelector('button[data-bs-target="#EnviarMensaje"]');

if (btnEnviarContacto) {
    btnEnviarContacto.addEventListener('click', () => {
        
        const nombreVal = document.getElementById('name').value;
        const emailVal = document.getElementById('email').value;
        const mensajeVal = document.getElementById('message').value;

        
        const objeto = { propiedad1: nombreVal, propiedad2: emailVal, temporal: "borrar" };
        
        delete objeto.temporal;
        console.log("Objeto base:", objeto);

        const ordenado = { estado: "Nuevo", ...objeto };
        console.log("Con Spread Operator:", ordenado);

        const objeto2 = { "tipo": "Consulta", "mensaje": mensajeVal };
        
        const composicion = Object.assign({}, ordenado, objeto2); 
        console.log("Composición (Object.assign):", composicion);

        const composicion2 = { ordenado, objeto2 }; 
        console.log("Composición 2 (Anidada):", composicion2);

        for (let prop in composicion2) {
            console.log(prop);
        }

        Object.entries(composicion2).forEach(([key, value]) => {
            console.log(`key: ${key}, value:`, value);
        });

        Object.entries(composicion2).forEach(([key, value]) => {
            Object.entries(value).forEach(([subKey, subValue]) => {
                console.log(`Sub-key: ${subKey}, value: ${subValue}`);
            });
        });
    });
}