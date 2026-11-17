// The browser entry point: index.html loads this file, which loads the
// global styles and mounts <App /> into the page.
//
// Why it matters: it's the first code that runs on every visit. Everything
// else is imported from here.

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App.tsx'

// Find the empty <div id="root"> in index.html and let React fill it.
// StrictMode runs extra checks in development (it doesn't change the live site).
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
