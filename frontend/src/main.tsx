import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource-variable/inter'
import '@fontsource/jetbrains-mono/400.css'
import App from './app/App'
import './styles.css'
import './workspace-design.css'

const client = new QueryClient({ defaultOptions: { queries: { staleTime: 10000, refetchOnWindowFocus: true } } })
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={client}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></React.StrictMode>)
