import express from 'express';
import hbs from 'hbs';
import path from 'path';
import session from 'express-session';
import bodyParser from 'body-parser';
import memoryStore from 'memorystore';
import { router as marketplaceRouter } from './routes/marketplace.mjs';
import { router as authRouter, initPassport } from './routes/auth.mjs';
import https from 'https';
import fs from 'fs';


// Workaround for lack of __dirname in ES6 modules
import dirname from './dirname.js';
const {__dirname} = dirname;

// Use express and set it up
const app = express();
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: false }));
app.use(express.static(path.join(__dirname, 'public')));
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'hbs');
hbs.registerPartials(path.join(__dirname, 'partials'));

// Configure express-session
const MemoryStore = memoryStore(session); 
app.use(session({ 
    secret: 'mo0oQWrfTdKDSNWKre5WEetFNDrSW63H',
    store: new MemoryStore({
        ttl: 60 * 10 * 1000000 // 10 minutes
    }),
    cookie: {
        secure: true
    },
    resave: false,
    saveUninitialized: false,
    name: 'marketplacecookie.sid'
}));
initPassport(app);

// Redirect from HTTP to HTTPS
app.use(function(req, res, next) {
    if (req.secure) {
        next();
    } else {
        const host = req.headers.host.substring(0, req.headers.host.indexOf(":"));
        res.redirect('https://' + host + ":3443" + req.url);
    }
});

// Set the routers
app.use('/', marketplaceRouter);
app.use('/', authRouter);

// Catch 404 and forward to error handler
app.use(function(req, res, next) {
    var err = new Error('Not Found');
    err.status = 404;
    next(err);
});

// Error handler
app.use(function(err, req, res, next) {
    // Only provide details about error in development
    if (req.app.get('env') === 'development') {
        res.locals.message = err.message;
    } else {
        if (err.status === 404) {
            res.locals.message = err.message;
        } else {
            res.locals.message = "An error occurred, please try again later";
        }
    }
    res.locals.error = req.app.get('env') === 'development' ? err : {};
 
    // render the error page
    res.status(err.status || 500);
    res.render('error');
});

// Handlebars helper to compare two strings
hbs.registerHelper('ifEquals', function(arg1, arg2, opts) {
    if (arg1 == arg2) {
        return opts.fn(this)
    } else {
        return opts.inverse(this)
    }
});

// Create and start HTTPS server
https.createServer({
    key: fs.readFileSync('server.key'),
    cert: fs.readFileSync('server.cert'),
    passphrase: 'tester'
}, app).listen(3443);    

export default app;