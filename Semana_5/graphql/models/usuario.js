const mongoose = require('mongoose');
const usuarioSchema = mongoose.Schema({
    nombre: String,
    gmail: String,
    pass: String,
});

module.exports = mongoose.model('Usuario', usuarioSchema);
