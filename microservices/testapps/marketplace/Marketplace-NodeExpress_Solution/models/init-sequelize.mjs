import Sequelize from 'sequelize';
import ProductModel from './product.mjs';
import PurchaseModel from './purchase.mjs';
import UserModel from './user.mjs';

const connectionDB = new Sequelize('marketplace', null, null, 
    {dialect: 'sqlite', storage: 'marketplace.sqlite3', logging: console.log}) 
const Product = ProductModel(connectionDB)
const Purchase = PurchaseModel(connectionDB)
const User = UserModel(connectionDB)

export {Product, Purchase, User}

connectionDB.sync().then(() => {
    console.log('Database & tables created (if not existing yet)')
})