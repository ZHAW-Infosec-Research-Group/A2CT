import express from 'express';
import passport from 'passport'; 
import passportLocal from 'passport-local';
import crypto from 'crypto';
import { readUser } from '../models/db-queries.mjs'; 
const LocalStrategy = passportLocal.Strategy; 

export const router = express.Router();

// Init passport and use session to identify authenticated requests
export function initPassport(app) { 
    app.use(passport.initialize()); 
    app.use(passport.session()); 
}

// Go to login page
router.get('/login', async (req, res, next) => {
    res.render('login');
});

// Process received username/password and - if correct - do the login
router.post('/login', function(req, res, next) {
    /* Check the credentials using LocalStrategy (see passport.use below). When done, 
       the specified callback function is called, which gets a user object (that
       contains username and role) as parameter. */
    passport.authenticate('local', function(err, user, info) {
        if (!user) {
            let messages = [];
            messages.push({message: 'Username or password wrong'});
            return res.render('login', {messages: messages});
        }
        req.logIn(user, function(err) {
            let tempPassport = req.session.passport;
            req.session.regenerate((err) => {
                req.session.passport = tempPassport;
                return res.redirect('admin_area');
            });
        });
    }) (req, res, next);
});

// Define the LocalStrategy that checks if the received credentials are correct
passport.use(new LocalStrategy( 
    async (username, password, done) => {
        const user = await readUser(username);
        if (user) {
            if (await verifyPasswordPBKDF2(password, user.Password)) {
                /* Credentials correct, specify that username and role are part of the profile
                   of a user; this will then be part of the user object that is received by 
                   the callback function specified in passport.authenticate above as user object */
                done(null, {username: username, role: user.Role});
                return;
            }
        }
        done(null, false);
    } 
));

/* Stores that data of the user (after successful authentication) in the session (username 
   and role). It's called by req.logIn above. */
passport.serializeUser(function(user, done) {
    done(null, user);
});

/* Makes sure that when receiving a request, the user data (username and role) stored in the 
   session is available via req.user */
passport.deserializeUser(async (user, done) => {
    done(null, user);
});

// Log out the current user
router.get('/logout', function(req, res, next) { 
    req.logout(); 
    res.redirect('products');
});

// Checks if the current request is authenticated
export function ensureAuthenticated(req, res, next) { 
    if (req.user) {
        next();
    } 
    else {
        res.redirect('login');
    }
}

// Check whether a password corresponds to a PBKDF2 hash
async function verifyPasswordPBKDF2(enteredPassword, storedPassword) {
    return new Promise((resolve, reject) => {
        const splitOriginalPassword = storedPassword.split(':');
        let salt = splitOriginalPassword[2];
        salt = Buffer.from(salt, 'base64');
        let storedHash = splitOriginalPassword[3];
        storedHash = Buffer.from(storedHash, 'base64');
        crypto.pbkdf2(enteredPassword, salt, 100000, 32, "SHA512", (err, computedHash) => {
            if (err) {
                reject(err);
            } else {
                resolve(crypto.timingSafeEqual(storedHash, computedHash));
            }
        });
    }).catch(e => {console.log(e)});
};