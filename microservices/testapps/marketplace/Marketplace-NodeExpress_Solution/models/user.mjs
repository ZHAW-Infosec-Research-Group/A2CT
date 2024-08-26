import Sequelize from 'sequelize';

export default (connectionDB) => {
    return connectionDB.define('User', {
        Username: {
            type: Sequelize.STRING(15),
            primaryKey: true
        },
        Password: Sequelize.STRING(200),
        Role: Sequelize.STRING(15)
    },
    {
        freezeTableName: true,
        timestamps: false
    })
}