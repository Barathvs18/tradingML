import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { api } from '../lib/api';
import { useQuery } from '@tanstack/react-query';
import { researchApi } from '../lib/research';
import { Activity, LayoutDashboard, PlayCircle, User } from 'lucide-react';

export default function Navbar() {
  const { isAuthenticated, logout } = useAuthStore();
  const navigate = useNavigate();
  const configuration = useQuery({ queryKey: ['research-config'], queryFn: async () => (await researchApi.get<{ mode: string; authentication_required: boolean }>('/app/analysis/config')).data, staleTime: Infinity });
  const localMode = configuration.data?.mode === 'local';

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // ignore
    } finally {
      logout();
      navigate('/login');
    }
  };

  return (
    <nav className="sticky top-0 z-30 mx-3 mt-3 flex flex-wrap gap-3 items-center justify-between rounded-2xl px-5 py-3 glass">
      <div className="flex items-center gap-2">
        <div className="grid h-8 w-8 place-items-center rounded-xl bg-[#5d75ff]/20 text-[#91a2ff]"><Activity className="h-4 w-4" /></div>
        <span className="text-base font-semibold tracking-tight text-white">Algo<span className="text-[#91a2ff]">Predict</span></span>
      </div>
      {!isAuthenticated && <div className="flex items-center gap-2">
        {localMode ? <Link to="/analyze" className="research-button-secondary text-xs">Open Indian market lab</Link> : <>
          <Link to="/login" className="research-button-secondary text-xs">Sign in</Link>
          <Link to="/register" className="research-button text-xs">Create account</Link>
        </>}
      </div>}
      
      {isAuthenticated && (
        <div className="flex flex-wrap items-center gap-3 sm:gap-6">
          <Link to="/analyze" className="text-sm text-indigo-300 hover:text-white">Indian market lab</Link>
          <Link to="/legacy/dashboard" className="flex items-center gap-2 text-slate-300 hover:text-primary transition-colors">
            <LayoutDashboard size={18} /> Legacy analysis
          </Link>
          <Link to="/simulate" className="flex items-center gap-2 text-slate-300 hover:text-primary transition-colors">
            <PlayCircle size={18} /> Simulate
          </Link>
          <Link to="/profile" className="flex items-center gap-2 text-slate-300 hover:text-primary transition-colors">
            <User size={18} /> Profile
          </Link>
          
          <button 
            onClick={handleLogout}
            className="ml-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-white/10"
          >
            Logout
          </button>
        </div>
      )}
    </nav>
  );
}
