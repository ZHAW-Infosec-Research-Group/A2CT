import Sequelize from 'sequelize';

export default (connectionDB) => {
    return connectionDB.define('Product', {
        ProductId: {
            type: Sequelize.INTEGER,
            primaryKey: true,
            autoIncrement: true
        },
        Code: Sequelize.STRING(10),
        Description: Sequelize.STRING(100),
        Price: Sequelize.DECIMAL(9, 2),
        Owner: Sequelize.STRING(15)
    },
    {
        freezeTableName: true,
        timestamps: false
    })
}