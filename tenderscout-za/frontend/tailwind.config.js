/** @type {import('tailwindcss').Config} */

/**
 * Tailwind CSS Configuration
 * 
 * This file configures Tailwind CSS for the TenderScout ZA frontend.
 * 
 * Features:
 *   - Custom brand color palette (green/teal)
 *   - Inter font as the default sans-serif typeface
 *   - Scans all JS/JSX/TS/TSX files for class usage
 */
export default {
  // ===========================================================================
  // CONTENT - Files to scan for Tailwind classes
  // ===========================================================================
  // Tailwind scans these files to determine which utility classes are used.
  // Unused classes are purged in production to minimize CSS bundle size.
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  
  // ===========================================================================
  // THEME - Custom design tokens
  // ===========================================================================
  theme: {
    extend: {
      // -----------------------------------------------------------------------
      // BRAND COLOR PALETTE (Green/Teal)
      // -----------------------------------------------------------------------
      // A fresh, professional green palette that conveys growth and trust.
      // 
      // Usage:
      //   text-brand-400    -> Green text
      //   bg-brand-600      -> Dark green background
      //   border-brand-200  -> Light green border
      colors: {
        brand: {
          50:  '#E1F5EE',  // Very light mint - backgrounds, hover states
          100: '#9FE1CB',  // Light mint - selected items, badges
          200: '#5DCAA5',  // Soft teal - borders, accents
          400: '#1D9E75',  // PRIMARY BRAND GREEN - buttons, links, focus rings
          600: '#0F6E56',  // Darker green - hover states, active elements
          800: '#085041',  // Deep green - text on light backgrounds
          900: '#04342C',  // Darkest green - headings, emphasis
        }
      },
      
      // -----------------------------------------------------------------------
      // FONTS
      // -----------------------------------------------------------------------
      // Inter is a modern, highly legible sans-serif designed for screens.
      // System fallbacks ensure text renders even if the font fails to load.
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  
  // ===========================================================================
  // PLUGINS
  // ===========================================================================
  // Additional Tailwind plugins can be added here.
  // Examples: @tailwindcss/forms, @tailwindcss/typography
  plugins: [],
}