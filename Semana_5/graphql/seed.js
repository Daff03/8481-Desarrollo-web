const mongoose = require('mongoose');
const Usuario = require('./models/usuario');
const usuarios = require('../usuarios.json');

async function seed() {
    await mongoose.connect('mongodb://localhost:27017/graphql');
    console.log('Conectado a MongoDB');

    await Usuario.deleteMany({});           
    await Usuario.insertMany(usuarios);  

    console.log(`✔ ${usuarios.length} usuarios insertados en la colección "usuarios"`);
    await mongoose.disconnect();
}

seed().catch((err) => {
    console.error('Error al cargar los datos:', err);
    process.exit(1);
});