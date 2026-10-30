import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { jwtDecode } from 'jwt-decode';
import { api } from '../lib/api';
import { errorMessage } from '../lib/research';
import { useAuthStore } from '../store/auth';

interface UserProfile { id: string; email: string; name: string; created_at: string }

export default function Profile() {
  const [name, setName] = useState('');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const token = useAuthStore(state => state.token);
  const userId = token ? jwtDecode(token).sub : undefined;
  const client = useQueryClient();
  const { data: profile, error, isPending } = useQuery({
    queryKey: ['profile', userId], enabled: !!userId,
    queryFn: async () => (await api.get<UserProfile>(`/app/user/${userId}`)).data,
  });
  const handleSave = async () => {
    if (!profile || !name.trim()) return;
    setSaving(true); setSaveError('');
    try {
      const { data } = await api.patch<UserProfile>(`/app/user/${profile.id}`, { name: name.trim() });
      client.setQueryData(['profile', userId], data); setEditing(false);
    } catch (problem) { setSaveError(errorMessage(problem)); }
    finally { setSaving(false); }
  };
  if (error) return <div role="alert" className="p-8 text-center text-rose-300">{errorMessage(error)}</div>;
  if (isPending || !profile) return <div role="status" className="p-8 text-center">Loading profile…</div>;

  return (
    <div className="max-w-2xl mx-auto w-full bg-surface p-8 rounded-xl border border-slate-700 shadow-xl mt-8">
      <h2 className="text-2xl font-bold mb-6">User Profile</h2>
      {saveError && <p role="alert" className="mb-4 text-rose-300">{saveError}</p>}
      
      <div className="flex flex-col gap-6">
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-1">Email</label>
          <input 
            type="email" 
            disabled 
            value={profile.email} 
            className="w-full bg-slate-800/50 border border-slate-700 rounded-md py-2 px-3 text-slate-400 cursor-not-allowed"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-1">Name</label>
          {editing ? (
            <div className="flex gap-2">
              <input 
                type="text" 
                value={name} 
                onChange={e => setName(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 focus:outline-none focus:border-primary text-white"
              />
              <button 
                onClick={handleSave}
                disabled={saving || !name.trim()}
                className="bg-primary hover:bg-blue-600 text-white px-4 py-2 rounded-md font-medium transition-colors"
              >
                Save
              </button>
              <button 
                onClick={() => { setEditing(false); setName(profile.name); }}
                className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-md font-medium transition-colors"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex justify-between items-center bg-slate-800/50 border border-slate-700 rounded-md py-2 px-3 text-white">
              <span>{profile.name}</span>
              <button 
                onClick={() => { setName(profile.name); setSaveError(''); setEditing(true); }}
                className="text-primary hover:underline text-sm font-medium"
              >
                Edit
              </button>
            </div>
          )}
        </div>
        
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-1">Member Since</label>
          <div className="w-full bg-slate-800/50 border border-slate-700 rounded-md py-2 px-3 text-slate-300">
            {new Date(profile.created_at).toLocaleDateString()}
          </div>
        </div>
      </div>
    </div>
  );
}
