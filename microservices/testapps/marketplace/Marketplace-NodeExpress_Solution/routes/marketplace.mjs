import express from 'express';
import {
    readProductsFilter, readProductsProductIds, readTotalPrice,
    createPurchase, createProduct, readPurchases, readProducts,
    readProductOwner, deleteProduct
} from '../models/db-queries.mjs';
import { ensureAuthenticated } from './auth.mjs';
import { check, validationResult } from 'express-validator';


export const router = express.Router();

// Get default page
router.get('/', async (req, res, next) => {
    res.render('products');
});

// Get products
router.get('/products', check('filter').isLength({max: 50}).withMessage("The search string must not be longer than 50 characters"),
    async (req, res, next) => {
        const errors = validationResult(req);
        if (errors.isEmpty()) {
            const productList = await readProductsFilter(req.query.filter)
            res.render('products', {
                filter: req.query.filter, productList: productList
            });
        } else {
            let messages = [];
            messages.push({message: errors.mapped().filter.msg});
            res.render('products', {messages: messages});
        }
    });

// Add product to cart
router.post('/cart_add', async (req, res, next) => {
    const cart = req.session.cart || [];
    if (!cart.includes(req.body.productId)) {
        cart.push(req.body.productId);
        req.session.cart = cart;
    }
    const productList = await readProductsProductIds(req.session.cart);
    res.render('cart', {productList: productList});
});

// Show cart
router.get('/cart', async (req, res, next) => {
    const cart = req.session.cart || [];
    const productList = await readProductsProductIds(cart);
    res.render('cart', {productList: productList});
});

// Go to checkout
router.get('/checkout', async (req, res, next) => {
    const cart = req.session.cart || [];
    const cartEmpty = (cart.length === 0);
    res.render('checkout', {cartEmpty: cartEmpty});
});

// Complete purchase
router.post('/purchase', [
        check('firstname').matches("^[a-zA-Z']{2,32}$").withMessage("Please insert a valid first name (between 2 and 32 characters)"),
        check('lastname').matches("^[a-zA-Z']{2,32}$").withMessage("Please insert a valid last name (between 2 and 32 characters)"),
        check('creditcardnumber').matches("^\\d{4}[ ]?\\d{4}[ ]?\\d{4}[ ]?\\d{4}$").withMessage("Please insert a valid credit card number (16 digits)")],
    async (req, res, next) => {
        const errors = validationResult(req);
        if (errors.isEmpty()) {
            const cart = req.session.cart || [];
            const totalPrice = await readTotalPrice(cart);
            let messages = [];
            if (totalPrice) {
                const result = await createPurchase(req.body.firstname, req.body.lastname,
                    req.body.creditcardnumber, totalPrice);
                if (result) {
                    messages.push({message: 'Your purchase has been completed, thank you for shopping with us'});
                } else {
                    messages.push({message: 'A problem occurred, please try again later'});
                }
            } else {
                messages.push({message: 'A problem occurred, please try again later'});
            }
            req.session.cart = [];
            res.render('products', {messages: messages});
        } else {
            res.render('checkout', {
                cartEmpty: false, validationErrors: errors.mapped()
            });
        }
    });

// Go to admin area
router.get('/admin_area', ensureAuthenticated, async (req, res, next) => {
    let purchaseView = false;
    let purchaseDelete = false;
    let productViewAddDelete = false;
    if (req.user.role === "sales") {
        purchaseView = true;
        purchaseDelete = true;
    } else if (req.user.role === "marketing") {
        purchaseView = true;
    } else if (req.user.role === "productmanager") {
        productViewAddDelete = true;
    }
    const purchaseList = await readPurchases();
    const productList = await readProducts();
    res.render('admin_area', {
        username: req.user.username,
        purchaseView: purchaseView, purchaseDelete: purchaseDelete,
        productViewAddDelete: productViewAddDelete,
        purchaseList: purchaseList, productList: productList
    });
});

// Delete purchase
router.post('/admin_purchase_delete', ensureAuthenticated, async (req, res, next) => {
    if (req.user.role === "sales") {
        await deletePurchase(req.body.purchaseId);
    }
    res.redirect('admin_area');
});

// Delete product
router.post('/admin_product_delete', ensureAuthenticated, async (req, res, next) => {
    if (req.user.role === "productmanager") {
        const owner = await readProductOwner(req.body.productId);
        if (owner === req.user.username) {
            const result = await deleteProduct(req.body.productId);
        }
    }
    res.redirect('admin_area');
});

// Go to add product
router.get('/admin_product_add', ensureAuthenticated, async (req, res, next) => {
    res.render('admin_product_add');

});

// Save new product
router.post('/admin_product_add', [
        check('code').matches("^[a-zA-Z0-9]{4}$").withMessage("Please insert a valid code (4 alphanumeric characters)"),
        check('description').matches("^[a-zA-Z']{2,32}$").withMessage("Please insert a valid description (10-100 characters: letters / digits / - / , / '"),
        check('price').isFloat({
            min: 0,
            max: 999999.99
        }).withMessage("Please insert a valid price (between 0 and 999'999.99)").isDecimal({decimal_digits: '0,2'}).withMessage("Please insert a valid price (at most two decimal places)")],
    ensureAuthenticated, async (req, res, next) => {
        const errors = validationResult(req);
        if (errors.isEmpty()) {
            await createProduct(req.body.code, req.body.description,
                req.body.price, req.user.username);
            res.redirect('admin_area');
        } else {
            res.render('admin_product_add', {
                validationErrors: errors.mapped()
            });
        }
    });