import '@fontsource-variable/inter'
import '@fontsource-variable/jetbrains-mono'
import './index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router'

import Shell from './app/Shell.tsx'
import Overview from './routes/Overview.tsx'
import { Bench } from './routes/Placeholder.tsx'
import Playground from './routes/Playground.tsx'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Overview />} />
            <Route path="playground" element={<Playground />} />
            <Route path="bench" element={<Bench />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
