const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');

const {ApolloServer, gql } = require('apollo-server-express');
const Usuario = require('./models/usuario');

mongoose.connect('mongodb://localhost:27017/graphql')
    .then(() => console.log('Conectado a MongoDB'))
    .catch((err) => console.error('Error de conexión:', err));
const typedefs = gql`
    type Usuario {
        id: ID!
        nombre: String!
        gmail: String!
        pass: String!
    }
    input UsuarioInput {
        nombre: String!
        pass: String!
        gmail: String!
    }
    type alert {
        message: String
    }
    type Query {
        getUsuarios: [Usuario]
        getUsuarioById(id: ID!): Usuario
    }
    type Mutation {
        addUsuario(input: UsuarioInput): Usuario
        updateUsuario(id: ID!, input: UsuarioInput): Usuario
        deleteUsuario(id: ID!): alert
    }
    
`;

const resolvers = {
    Query: {
        async getUsuarios(obj) {
            const usuarios = await Usuario.find();
            return usuarios;
        },
        async getUsuarioById(obj, {id}) {
            const usuarioSearch = await Usuario.findById(id);
            if (usuarioSearch == null) {
                return null;
            } else{
                return usuarioSearch;
            }
        },
    },
    Mutation: {
        async addUsuario(obj, {input}) {
            const usuario = new Usuario(input);
            await usuario.save();
            return usuario;
        },
        async updateUsuario(obj, {id, input}) {
            const usuario = await Usuario.findByIdAndUpdate(id, input)
            return usuario;
        },
        async deleteUsuario(obj, {id}) {
            await Usuario.deleteOne({ _id: id });
            return {
                message: "Usuario eliminado"
            }
        }
    }
}

let apolloServer = null
const corsOption ={
    origin: 'http://localhost:8090',
    credentials: false
}

async function startServer() {
    apolloServer = new ApolloServer({ typeDefs: typedefs, resolvers, corsOption});
    await apolloServer.start();
    apolloServer.applyMiddleware({ app, cors: false });
}

startServer();

const app = express();
app.use(cors());
app.listen(8090, function() {
    console.log(`Server ready at http://localhost:8090${apolloServer.graphqlPath}`);
} );