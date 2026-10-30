import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './store/auth';
import { refreshSession } from './lib/api';
import { jwtDecode } from 'jwt-decode';

// Layout & Wrapper
import Protected from './components/Protected';
import Navbar from './components/Navbar';

// Pages
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Simulate = lazy(() => import('./pages/Simulate'));
const Profile = lazy(() => import('./pages/Profile'));
const OAuthCallback = lazy(() => import('./pages/OAuthCallback'));
const Landing = lazy(() => import('./pages/Landing'));
const Analyze = lazy(() => import('./pages/Analyze'));
const PredictionHistory = lazy(() => import('./pages/PredictionHistory'));
const ModelPerformance = lazy(() => import('./pages/ModelPerformance'));
const Strategies = lazy(() => import('./pages/Strategies'));
const Portfolio = lazy(() => import('./pages/Portfolio'));
const Compare = lazy(() => import('./pages/Compare'));
const Intraday = lazy(() => import('./pages/Intraday'));

function createQueryClient(identity: string | undefined) { return new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      meta: { owner: identity },
    },
  },
}); }

function App() {
  const { setToken, token } = useAuthStore();
  const identity = token ? jwtDecode(token).sub : 'anonymous';
  // A new cache on account changes prevents one user's research being shown to another.
  const queryClient = useMemo(() => createQueryClient(identity), [identity]);
  const [initializing, setInitializing] = useState(() => window.location.pathname !== '/oauth/callback');

  useEffect(() => {
    if (window.location.pathname === '/oauth/callback') return;
    let active = true;
    const initialize = async () => {
      try {
        // Configuration is public; avoid the authenticated client interceptor here.
        // A 401 from a protected endpoint must not trigger refresh while deciding
        // whether this deployment requires authentication.
        const apiBase = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '' : '/api');
        const response = await fetch(`${apiBase}/app/analysis/config`);
        if (!response.ok) throw new Error('Could not load application configuration');
        const mode = await response.json() as { authentication_required: boolean };
        if (!mode.authentication_required) { setToken(null); return; }
        await refreshSession();
      } catch { if (active) setToken(null); }
      finally { if (active) setInitializing(false); }
    };
    initialize();
    return () => { active = false; };
  }, [setToken]);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen flex flex-col">
          <Navbar />
          <main className="flex-1 flex flex-col p-4">
            <Suspense fallback={<div role="status" className="p-12 text-center text-slate-400">Loading workspace…</div>}>
            {initializing ? <div className="grid min-h-[50vh] place-items-center text-sm text-slate-400">Opening your workspace…</div> : <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/oauth/callback" element={<OAuthCallback />} />
              <Route path="/analyze" element={<Analyze />} />
              <Route path="/history" element={<PredictionHistory />} />
              <Route path="/performance" element={<ModelPerformance />} />
              <Route path="/strategies" element={<Strategies />} />
              <Route path="/portfolio" element={<Portfolio />} />
              <Route path="/compare" element={<Compare />} />
              <Route path="/intraday" element={<Protected><Intraday /></Protected>} />
              
              <Route path="/dashboard" element={
                <Protected>
                  <Analyze />
                </Protected>
              } />
              <Route path="/legacy/dashboard" element={<Protected><Dashboard /></Protected>} />
              
              <Route path="/simulate" element={
                <Protected>
                  <Simulate />
                </Protected>
              } />
              
              <Route path="/profile" element={
                <Protected>
                  <Profile />
                </Protected>
              } />

              <Route path="*" element={<Navigate to="/analyze" replace />} />
            </Routes>}
            </Suspense>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
