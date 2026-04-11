import client from './client'

export const getBalance = () => client.get('/credits/balance')
export const topUp = (pkg) => client.post('/credits/topup', { package: pkg })
export const getTransactions = () => client.get('/user/transactions')
