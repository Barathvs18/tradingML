import { Navigate } from 'react-router-dom';
import type { ReactElement } from 'react';
import { useAuthStore } from '../store/auth';

const Protected = ({ children }: { children: ReactElement }) => {
  const { isAuthenticated } = useAuthStore();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

export default Protected;
