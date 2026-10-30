import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api, API_URL } from '../lib/api';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../store/auth';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const configuration = useQuery({ queryKey: ['research-config'], queryFn: async () => (await api.get('/app/analysis/config')).data });
  const navigate = useNavigate();
  const { setToken } = useAuthStore();
  const googleLogin = () => { window.location.assign(`${API_URL}/auth/oauth/google/start`); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    
    try {
      const res = await api.post('/auth/login', { email, password });
      setToken(res.data.access_token);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally { setBusy(false); }
  };

  return (
    <div className="flex flex-col items-center justify-center flex-1 px-4">
      <div className="glass w-full max-w-md rounded-3xl p-8">
        <p className="mb-2 text-center text-xs font-medium uppercase tracking-[0.24em] text-[#91a2ff]">AlgoPredict</p>
        <h2 className="mb-6 text-center text-2xl font-semibold text-white">Welcome back</h2>
        
        {error && <div className="mb-4 p-3 bg-danger/20 text-danger rounded-md text-sm">{error}</div>}
        
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-slate-400 mb-1">Email</label>
            <input 
              type="email" 
              id="login-email" autoComplete="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary text-white" 
            />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-sm font-medium text-slate-400 mb-1">Password</label>
            <input 
              type="password" 
              id="login-password" autoComplete="current-password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary text-white" 
            />
          </div>
          <button 
            type="submit" 
            disabled={busy}
            className="premium-button mt-4 rounded-xl py-2.5 text-white font-medium transition-all"
          >
            {busy ? 'Signing in…' : 'Login'}
          </button>
        </form>
        {configuration.data?.google_oauth_enabled && <><div className="my-5 flex items-center gap-3 text-xs text-slate-500"><span className="h-px flex-1 bg-slate-700" />OR<span className="h-px flex-1 bg-slate-700" /></div>
        <button onClick={googleLogin} type="button" className="w-full rounded-md border border-slate-600 bg-slate-800 py-2 text-sm font-medium text-white hover:bg-slate-700">Continue with Google</button></>}
        <p className="mt-6 text-center text-sm text-slate-400">
          Don't have an account? <Link to="/register" className="text-primary hover:underline">Register</Link>
        </p>
      </div>
    </div>
  );
}
