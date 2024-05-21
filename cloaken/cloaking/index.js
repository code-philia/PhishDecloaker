require('dotenv').config();
const express = require('express');
const vhost = require('vhost');
const path = require('path');
const mongoose = require('mongoose');

const dashboardRoutes = require('./routes/dashboard.js');
const honeypotRoutes = require('./routes/honeypot.js');

const main = async () => {
    const app = express();
    const port = process.env.PORT;

    // connect to database
    const db = await mongoose.connect(process.env.MONGODB_URI);
    console.log('Connected to MongoDB ' + db.connection.name);

    // view engine setup
    app.set('views', path.join(__dirname, 'views'));
    app.set('view engine', 'ejs');

    // ignore favicon
    app.get('/favicon.ico', (req, res) => res.status(200));

    // other settings
    app.use(express.static(__dirname + '/public'));
    app.use(express.json());
    app.use(express.text());
    app.use(express.urlencoded({ extended: false }));

    // log information about visitor
    app.use((req, res, next) => {
        var timestamp = new Date().toISOString();
        var fullUrl = req.protocol + '://' + req.get('host') + req.originalUrl;
        console.log(`${timestamp} | ${fullUrl}`);
        next();
    });

    // routing by subdomain
    app.use(vhost("localhost", dashboardRoutes))
        .use(vhost('www.localhost', dashboardRoutes))
        .use(vhost('*.localhost', honeypotRoutes));

    // 404 handler
    app.use((req, res, next) => {
        res.status(404).render('error', { message: "Not Found" });
    });

    // error handler
    app.use((err, req, res, next) => {
        if (res.headersSent) {
            return next(err);
        }
        res.status(500).render('error', { message: err });
    });

    app.listen(port, () => {
        console.log('App now listening on port ' + port);
    });

    return app;
};

main().catch((err) => console.log({ err }));