import Sequelize from 'sequelize';

export default (connectionDB, type) => {
    return connectionDB.define('Purchase', {
        PurchaseId: {
            type: Sequelize.INTEGER,
            primaryKey: true,
            autoIncrement: true
        },
        Firstname: Sequelize.STRING(50),
        Lastname: Sequelize.STRING(50),
        CreditCardNumber: Sequelize.STRING(100),
        TotalPrice: Sequelize.DECIMAL(10, 2)
    },
    {
        freezeTableName: true,
        timestamps: false
    })
}