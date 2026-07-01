// components/ErrorBoundary.jsx
// React error boundary that catches render‑time errors in the component tree
// and shows a user‑friendly fallback UI instead of a blank screen.
// It also logs the error and shows a toast notification via react‑hot‑toast.

import React from 'react';
import toast from 'react-hot-toast';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    // Track whether an error has occurred and the error itself
    this.state = { hasError: false, error: null };
  }

  // Update state so the next render shows the fallback UI
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  // Log the error (console + toast) for debugging
  componentDidCatch(error, errorInfo) {
    console.error('App crashed:', error, errorInfo);
    toast.error('Something went wrong. Please refresh the page.');
  }

  render() {
    if (this.state.hasError) {
      // Fallback UI when any child component throws during rendering
      return (
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <h1 className="text-2xl font-bold mb-4">Something went wrong</h1>
            <p className="text-gray-600 mb-4">Please refresh the page</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg"
            >
              Refresh
            </button>
          </div>
        </div>
      );
    }

    // No error – render children normally
    return this.props.children;
  }
}

export default ErrorBoundary;