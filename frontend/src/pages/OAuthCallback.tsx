import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuthStore } from '../store/auth';

export default function OAuthCallback() {
  const navigate = useNavigate();
  const { setToken } = useAuthStore();
  const code = new URLSearchParams(window.location.search).get('code');
  const [error, setError] = useState(code ? 'Completing secure sign-in…' : 'OAuth login could not be completed.');
  const exchanged = useRef(false);
  useEffect(() => {
    if (exchanged.current) return;
    exchanged.current = true;
    if (!code) return;
    window.history.replaceState(null, '', '/oauth/callback');
    api.post('/auth/oauth/exchange', { code }).then(({ data }) => {
      setToken(data.access_token); navigate('/dashboard', { replace: true });
    }).catch((err) => setError(err.response?.data?.detail || 'OAuth login has expired. Please try again.'));
  }, [navigate, setToken, code]);
  return <div className="m-auto rounded-xl border border-slate-700 bg-slate-900 px-8 py-6 text-sm text-slate-300">{error}</div>;
}
