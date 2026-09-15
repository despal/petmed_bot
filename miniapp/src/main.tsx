import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import LiveApp from './LiveApp.tsx'

const useMocks = import.meta.env.VITE_USE_MOCKS === 'true'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {useMocks ? <App /> : <LiveApp />}
  </StrictMode>,
)
