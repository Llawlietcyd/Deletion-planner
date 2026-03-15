import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  completeOnboarding as completeOnboardingRequest,
  getSession,
  login as loginRequest,
  logout as logoutRequest,
  setSessionToken,
} from '../http/api';

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshSession = async () => {
    setLoading(true);
    try {
      const data = await getSession();
      setSession(data);
      return data;
    } catch (err) {
      if (err?.status === 401 || err?.status === 403) {
        setSessionToken('');
        setSession(null);
      }
      return null;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshSession().catch(() => {});
  }, []);

  const login = async (displayName, password, birthday, gender) => {
    const data = await loginRequest(displayName, password, birthday, gender);
    setSessionToken(data.session_token || '');
    setSession(data);
    return data;
  };

  const logout = async () => {
    const data = await logoutRequest();
    setSessionToken('');
    setSession(data);
    return data;
  };

  const completeOnboarding = async (payload) => {
    const data = await completeOnboardingRequest(payload);
    if (data.session?.session_token) {
      setSessionToken(data.session.session_token);
    }
    setSession(data.session);
    return data;
  };

  const value = useMemo(
    () => ({
      session,
      loading,
      refreshSession,
      login,
      logout,
      completeOnboarding,
    }),
    [session, loading]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within SessionProvider');
  }
  return context;
}
