// =============================================================================
// LOADING SPINNER COMPONENT (Add this above PrivateRoute)
// =============================================================================
/**
 * LoadingSpinner - Reusable loading indicator
 * 
 * @param {Object} props
 * @param {boolean} props.fullScreen - Whether to take up full viewport height
 * @param {string} props.size - Size of spinner (sm, md, lg)
 * @param {string} props.message - Optional loading message to display
 */
function LoadingSpinner({ fullScreen = false, size = 'md', message }) {
  // Size mappings for the spinner
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-2',
    lg: 'w-10 h-10 border-3',
  }
  
  const spinnerSize = sizeClasses[size] || sizeClasses.md
  const containerClasses = fullScreen
    ? "min-h-screen flex flex-col items-center justify-center"
    : "flex flex-col items-center justify-center p-8"
  
  return (
    <div className={containerClasses}>
      <div 
        className={`${spinnerSize} border-brand-400 border-t-transparent rounded-full animate-spin`} 
      />
      {message && (
        <p className="mt-3 text-sm text-gray-500">{message}</p>
      )}
    </div>
  )
}

// =============================================================================
// PRIVATE ROUTE GUARD (Updated with LoadingSpinner)
// =============================================================================
/**
 * PrivateRoute - Protects routes that require authentication
 * 
 * Behavior:
 *   - If auth is still loading: shows a loading spinner with message
 *   - If user is authenticated: renders the children (protected page)
 *   - If user is NOT authenticated: redirects to /login
 * 
 * The loading state is crucial to prevent:
 *   - Flash of login page before auth check completes
 *   - Unauthorized API calls that would fail
 *   - Poor user experience with flickering content
 * 
 * @param {React.ReactNode} children - The protected page component to render
 */
function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  
  // ===========================================================================
  // LOADING STATE
  // ===========================================================================
  // Show loading spinner while checking authentication status.
  // This typically takes < 100ms if token is cached, or ~500ms if validating.
  if (loading) {
    return (
      <LoadingSpinner 
        fullScreen 
        size="lg" 
        message="Verifying your session..." 
      />
    )
  }
  
  // ===========================================================================
  // AUTHENTICATED STATE
  // ===========================================================================
  // User is authenticated → render the protected page
  if (user) {
    return children
  }
  
  // ===========================================================================
  // UNAUTHENTICATED STATE
  // ===========================================================================
  // User is NOT authenticated → redirect to login page
  // replace=true prevents the login page from being added to browser history,
  // so users can't accidentally navigate "back" to a protected page after logout.
  return <Navigate to="/login" replace />
}