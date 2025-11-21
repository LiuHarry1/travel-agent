import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ChatSessionsProvider } from './hooks/useChatSessions'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ChatSessionsProvider>
      <App />
    </ChatSessionsProvider>
  </StrictMode>,
)
