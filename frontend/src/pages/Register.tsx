import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api, API_URL } from '../lib/api';
import { useQuery } from '@tanstack/react-query';

export default function Register() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const configuration = useQuery({ queryKey: ['research-config'], queryFn: async () => (await api.get('/app/analysis/config')).data });
  const googleLogin = () => { window.location.assign(`${API_URL}/auth/oauth/google/start`); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    
    try {
      await api.post('/auth/register', { email, name, password });
      navigate('/login');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((issue) => issue.msg || 'Invalid registration details.').join(' ')
        : detail;
      setError(message || 'Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center flex-1 px-4">
      <div className="glass w-full max-w-md rounded-3xl p-8">
        <p className="mb-2 text-center text-xs font-medium uppercase tracking-[0.24em] text-[#91a2ff]">AlgoPredict</p>
        <h2 className="mb-6 text-center text-2xl font-semibold text-white">Create your workspace</h2>
        
        {error && <div className="mb-4 p-3 bg-danger/20 text-danger rounded-md text-sm">{error}</div>}
        
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label htmlFor="register-name" className="block text-sm font-medium text-slate-400 mb-1">Name</label>
            <input 
              type="text" 
              required
              value={name}
              id="register-name" maxLength={100} autoComplete="name"
              onChange={e => setName(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary text-white" 
            />
          </div>
          <div>
            <label htmlFor="register-email" className="block text-sm font-medium text-slate-400 mb-1">Email</label>
            <input 
              type="email" 
              required
              value={email}
              id="register-email" autoComplete="email"
              onChange={e => setEmail(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary text-white" 
            />
          </div>
          <div>
            <label htmlFor="register-password" className="block text-sm font-medium text-slate-400 mb-1">Password</label>
            <input 
              type="password" 
              required
              minLength={8}
              value={password}
              id="register-password" maxLength={128} autoComplete="new-password"
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary text-white" 
            />
            <p className="mt-1 text-xs text-slate-500">Use at least 8 characters.</p>
          </div>
          <button 
            type="submit" 
            disabled={isSubmitting}
            className="premium-button mt-4 rounded-xl py-2.5 text-white font-medium transition-all disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? 'Creating account...' : 'Register'}
          </button>
        </form>
        {configuration.data?.google_oauth_enabled && <><div className="my-5 flex items-center gap-3 text-xs text-slate-500"><span className="h-px flex-1 bg-slate-700" />OR<span className="h-px flex-1 bg-slate-700" /></div>
        <button onClick={googleLogin} type="button" className="w-full rounded-md border border-slate-600 bg-slate-800 py-2 text-sm font-medium text-white hover:bg-slate-700">Sign up with Google</button></>}
        <p className="mt-6 text-center text-sm text-slate-400">
          Already have an account? <Link to="/login" className="text-primary hover:underline">Login</Link>
        </p>
      </div>
    </div>
  );
}
