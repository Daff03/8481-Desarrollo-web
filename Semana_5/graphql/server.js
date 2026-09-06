const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');

const {ApolloServer, gql } = require('apollo-server-express');
const Usuario = require('./models/usuario');

