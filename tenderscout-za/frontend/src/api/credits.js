/**
 * File: src/api/credits.js
 * Purpose: Credit Management API Service
 * 
 * This module provides functions for all credit-related API calls:
 *   - Checking current credit balance
 *   - Purchasing additional credits (top-up)
 *   - Viewing transaction history
 * 
 * Credits are the currency of the platform:
 *   - New users receive 5 free credits on registration
 *   - Each search result consumes 1 credit
 *   - Additional credits can be purchased via top-up packages
 * 
 * All functions use the pre-configured Axios client from client.js,
 * which automatically handles token injection and 401 redirects.
 */

import client from './client'

// =============================================================================
// CREDIT BALANCE
// =============================================================================

/**
 * Get the current user's credit balance
 * 
 * Endpoint: GET /credits/balance
 * 
 * Requires Authentication: Yes (JWT token required)
 * 
 * Response:
 *   {
 *     "balance": 15.5,           // Current credit balance
 *     "rand_value": 155.0        // Approximate value in ZAR (1 credit ≈ R10)
 *   }
 * 
 * Usage:
 *   - Display balance in header/navbar
 *   - Check if user has enough credits before search
 *   - Show balance on top-up page
 *   - Update balance after search or top-up
 * 
 * This endpoint should be called:
 *   - On app initialization (to show current balance)
 *   - After successful login
 *   - After completing a search (balance decreases)
 *   - After successful top-up (balance increases)
 * 
 * Example:
 *   const response = await getBalance()
 *   console.log(`You have ${response.data.balance} credits`)
 * 
 * @returns {Promise} Axios promise resolving to balance object
 */
export const getBalance = () => client.get('/credits/balance')

// =============================================================================
// CREDIT TOP-UP (Purchase)
// =============================================================================

/**
 * Purchase additional credits
 * 
 * Endpoint: POST /credits/topup
 * 
 * Requires Authentication: Yes (JWT token required)
 * 
 * Request Body:
 *   - package: string - Package identifier ("100", "250", or "500")
 * 
 * Available Packages:
 *   - "100": 100 credits for R10  (R0.10 per credit)
 *   - "250": 250 credits for R25  (R0.10 per credit)
 *   - "500": 500 credits for R50  (R0.10 per credit)
 * 
 * Response (on success):
 *   {
 *     "success": true,
 *     "credits_added": 100,
 *     "new_balance": 115.5,
 *     "message": "100 credits added successfully"
 *   }
 * 
 * Error Responses:
 *   - 400: Invalid package (must be "100", "250", or "500")
 *   - 401: Unauthorized (token missing/invalid)
 * 
 * Note: This is currently a DEMO implementation.
 * In production, this would integrate with:
 *   - PayFast (South African payment gateway)
 *   - Stripe (International payments)
 *   - Ozow (Instant EFT)
 * 
 * After successful top-up:
 *   - User's balance is immediately updated
 *   - A transaction record is created
 *   - UI should refresh the displayed balance
 * 
 * Example:
 *   try {
 *     const response = await topUp("100")
 *     toast.success(`Added ${response.data.credits_added} credits!`)
 *     // Refresh balance display
 *     await refreshBalance()
 *   } catch (error) {
 *     toast.error('Failed to add credits')
 *   }
 * 
 * @param {string} pkg - Package identifier ("100", "250", or "500")
 * @returns {Promise} Axios promise resolving to top-up result
 */
export const topUp = (pkg) => client.post('/credits/topup', { package: pkg })

// =============================================================================
// TRANSACTION HISTORY
// =============================================================================

/**
 * Get the user's transaction history
 * 
 * Endpoint: GET /user/transactions
 * 
 * Requires Authentication: Yes (JWT token required)
 * 
 * Response:
 *   Array of transaction objects (most recent first, max 50):
 *   [
 *     {
 *       "id": 789,
 *       "amount": 5.0,
 *       "transaction_type": "credit",        // "credit" or "debit"
 *       "description": "Welcome bonus — 5 free credits",
 *       "created_at": "2026-04-20T09:15:00Z"
 *     },
 *     {
 *       "id": 790,
 *       "amount": 15.0,
 *       "transaction_type": "debit",
 *       "description": "Search: 15 results",
 *       "created_at": "2026-04-21T14:30:00Z"
 *     },
 *     {
 *       "id": 791,
 *       "amount": 100.0,
 *       "transaction_type": "credit",
 *       "description": "Top-up: R100 — 100 credits",
 *       "created_at": "2026-04-22T11:00:00Z"
 *     }
 *   ]
 * 
 * Transaction Types:
 *   - "credit": Credits added (welcome bonus, top-up, refund)
 *   - "debit": Credits spent (search results)
 * 
 * Usage:
 *   - Account page: Display transaction history table
 *   - Credit usage analytics
 *   - Billing/invoice generation
 * 
 * Example:
 *   const response = await getTransactions()
 *   response.data.forEach(tx => {
 *     console.log(`${tx.transaction_type}: ${tx.amount} credits - ${tx.description}`)
 *   })
 * 
 * @returns {Promise} Axios promise resolving to transaction array
 */
export const getTransactions = () => client.get('/user/transactions')