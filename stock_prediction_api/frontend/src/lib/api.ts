import axios from 'axios';
import { useAuthStore } from '../store/auth';

// Vercel forwards /api/* to the Render service. Keeping requests same-origin
// preserves secure HTTP-only refresh cookies across the split deployment.
export const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '' : '/api');

export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true, // Important for refresh cookie
  timeout: 30000,
});

let refreshing: Promise<string> | null = null;

export function refreshSession(): Promise<string> {
  if (!refreshing) {
    const expectedToken = useAuthStore.getState().token;
    const performRefresh = () => axios.post(`${API_URL}/auth/refresh`, {}, { withCredentials: true, timeout: 10000 });
    // Web Locks also serialize rotations across tabs that share the refresh cookie.
    const request = navigator.locks ? navigator.locks.request('algopredict-session-refresh', performRefresh) : performRefresh();
    refreshing = request
      .then(({ data }) => {
        if (useAuthStore.getState().token !== expectedToken) throw new Error('Session changed while refreshing');
        useAuthStore.getState().setToken(data.access_token);
        return data.access_token as string;
      })
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}

// Add token to requests
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 and silent refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // If error is 401 and we haven't retried yet
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry &&
        !originalRequest.url?.startsWith('/auth/') && useAuthStore.getState().isAuthenticated) {
      originalRequest._retry = true;
      const previousToken = useAuthStore.getState().token;
      
      try {
        // Attempt to refresh the token using the httpOnly cookie
        const newToken = await refreshSession();
        
        // Update store
        useAuthStore.getState().setToken(newToken);
        
        // Update header and retry
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, logout
        if (useAuthStore.getState().token === previousToken) useAuthStore.getState().logout();
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);
