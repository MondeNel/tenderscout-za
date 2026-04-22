/**
 * File: src/main.jsx
 * Purpose: Application Entry Point
 * 
 * This is the root file that initializes the React application.
 * It sets up:
 *   - React DOM rendering
 *   - BrowserRouter for client-side routing
 *   - ErrorBoundary for graceful error handling
 *   - React Hot Toast for notifications
 *   - Global styles via index.css
 * 
 * This file is the first thing that executes when the app loads.
 */

import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'  // ← ADD THIS IMPORT
import './index.css'

// =============================================================================
// APPLICATION INITIALIZATION
// =============================================================================
// ReactDOM.createRoot is the modern React 18 way to render the app.
// It enables concurrent features and automatic batching for better performance.

ReactDOM.createRoot(document.getElementById('root')).render(
  // ===========================================================================
  // React.StrictMode - Development-Only Wrapper
  // ===========================================================================
  // StrictMode helps catch common bugs by:
  //   - Detecting unsafe lifecycle methods
  //   - Warning about legacy string ref usage
  //   - Detecting unexpected side effects by double-invoking functions
  // 
  // NOTE: This only runs in development, not production.
  <React.StrictMode>
    
    {/* =========================================================================
        BrowserRouter - Client-Side Routing Provider
        =========================================================================
        BrowserRouter uses the HTML5 History API to keep UI in sync with the URL.
        It enables navigation without full page reloads.
        
        All routes defined in App.jsx will work within this context.
        The current location is stored in the browser's address bar.
    */}
    <BrowserRouter>
      
      {/* =====================================================================
          ErrorBoundary - Graceful Error Handling
          =====================================================================
          Catches JavaScript errors anywhere in the child component tree,
          logs those errors, and displays a fallback UI instead of crashing.
          
          This prevents the entire app from going blank when an error occurs.
      */}
      <ErrorBoundary>
        {/* =====================================================================
            App - Root Component
            =====================================================================
            The main application component that contains:
              - Authentication context provider
              - Route definitions for all pages
              - Layout wrapper (header, sidebar, main content)
        */}
        <App />
      </ErrorBoundary>
      
      {/* =====================================================================
          Toaster - Toast Notification System
          =====================================================================
          react-hot-toast provides non-blocking notifications.
          
          Configuration:
            - position: "top-right" - Appears in upper right corner
            - duration: 4000ms - Auto-dismiss after 4 seconds
            - Custom styling to match the app's design system
            
          Usage throughout the app:
            import toast from 'react-hot-toast';
            toast.success('Tender saved!');
            toast.error('Failed to load tenders');
            toast.loading('Searching...');
      */}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,                        // 4 seconds before auto-dismiss
          style: {
            background: '#fff',                  // White background
            color: '#111',                       // Dark text for contrast
            border: '1px solid #e5e7eb',        // Subtle gray border (Tailwind gray-200)
            borderRadius: '10px',                // Rounded corners
            fontSize: '13px',                    // Compact, readable text
          },
        }}
      />
      
    </BrowserRouter>
  </React.StrictMode>
)