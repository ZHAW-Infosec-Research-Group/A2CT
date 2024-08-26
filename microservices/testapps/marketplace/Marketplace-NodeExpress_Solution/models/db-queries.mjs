import sqlite3 from 'sqlite3';
import Sequelize from 'sequelize'
import {Product, Purchase, User} from './init-sequelize.mjs';

const Op = Sequelize.Op;

export async function readProductsFilter(filter) {
    if (!filter) {
        filter = '';
    }
    const products = await Product.findAll({ where: { Description: {[Op.like]: "%" + filter + "%"}}})
        .catch(e => {console.log(e)});
    let productList = [];
    if (products) { 
        let product; 
        for (product of products) {
            productList.push({ productId: product.ProductId, code: product.Code, 
                description: product.Description, price: product.Price, 
                owner: product.Owner });
        }
        return productList;
    } 
}

function toProductList(products) {
    let product;
    const productList = [];
    for (product of products) {
        productList.push({ productId: product.ProductId, code: product.Code, 
            description: product.Description, price: product.Price, owner: product.Owner });
    }
    return productList;
}

export async function readProducts() {
    return readProductsFilter("");
}

export async function readProductsProductIds(productIds) {
    const products = await Product.findAll({ where: { ProductId: {[Op.in]: productIds}}})
        .catch(e => {console.log(e)});
    let productList = [];
    if (products) { 
        let product; 
        for (product of products) {
            productList.push({ productId: product.ProductId, code: product.Code, 
                description: product.Description, price: product.Price, 
                owner: product.Owner });
        }
        return productList;
    } 
}

export async function readProductOwner(productId) {
    const product = await Product.findOne({ where: { ProductId: productId }})
        .catch(e => {console.log(e)});
    if (product) {
        return product.Owner;
    } else {
        return "";
    }
}

export async function readTotalPrice(productIds) {
    const totalPrice = await Product.sum('price', { where: { ProductId: {[Op.in]: productIds}}})
        .catch(e => {console.log(e)});
    return totalPrice; 
}

export async function createPurchase1(firstName, lastName, creditCardNumber, totalPrice) {
    const result = await Purchase.create({Firstname: firstName, Lastname: lastName, 
        CreditCardNumber: creditCardNumber, TotalPrice: totalPrice}).catch(e => {console.log(e)});
    if (!result) {
        return false;
    }
    return true;
}

export async function createPurchase(firstName, lastName, creditCardNumber, totalPrice) {
    const result = await Purchase.create({ Firstname: firstName, Lastname: lastName, 
        CreditCardNumber: creditCardNumber, TotalPrice: totalPrice }).catch(e => {console.log(e)});
    if (!result) {
        return false;
    }
    return true;
}

export async function readPurchases() {
    const purchases = await Purchase.findAll()
        .catch(e => {console.log(e)});
    let purchaseList = [];
    if (purchases) { 
        let purchase;
        for (purchase of purchases) {
            purchaseList.push({ purchaseId: purchase.PurchaseId, firstName: purchase.Firstname, 
                lastName: purchase.Lastname, creditCardNumber: purchase.CreditCardNumber, 
                totalPrice: purchase.TotalPrice });
        }
        return purchaseList;
    } 
}

export async function deletePurchase(purchaseID) {
    const purchase = await Purchase.findOne({ where: { PurchaseId: purchaseID }}).catch(e => {console.log(e)});
    if (purchase) {
        return purchase.destroy(); 
    }
    return false;
}

export async function deleteProduct(productID) {
    const product = await Product.findOne({ where: { ProductId: productID }}).catch(e => {console.log(e)});
    if (product) {
        return product.destroy(); 
    }
    return false;
}

export async function createProduct(code, description, price, owner) {
    const result = await Product.create({ Code: code, Description: description, 
        Price: price, Owner: owner }).catch(e => {console.log(e)});
    if (!result) {
        return false;
    }
    return true;
}

export async function readUser(username) {
    const user = await User.findOne({ where: { Username: username }})
        .catch(e => {console.log(e)});
    return user;
}