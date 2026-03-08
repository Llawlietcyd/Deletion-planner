import React, { useState, useCallback, useRef, createContext, useContext } from 'react';

const ToastContext = createContext();

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null);
  const timerRef = useRef(null);

  const showToast = useCallback((message, undoAction = null, duration = 5000) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setToast({ message, undoAction });
    timerRef.current = setTimeout(() => {
      setToast(null);
    }, duration);
  }, []);

  const dismissToast = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setToast(null);
  }, []);

  const handleUndo = useCallback(async () => {
    if (toast?.undoAction) {
      try {
        await toast.undoAction();
      } catch (err) {
        console.error('Undo failed:', err);
      }
    }
    dismissToast();
  }, [toast, dismissToast]);

  return (
    <ToastContext.Provider value={{ showToast, dismissToast }}>
      {children}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] animate-slide-up">
          <div className="flex items-center gap-3 px-5 py-3 rounded-2xl bg-slate-800 dark:bg-slate-700 text-white shadow-lg min-w-[280px]">
            <span className="text-sm flex-1">{toast.message}</span>
            {toast.undoAction && (
              <button
                onClick={handleUndo}
                className="text-sm font-semibold text-[#007AFF] hover:text-[#4DA3FF] transition-colors"
              >
                Undo
              </button>
            )}
            <button
              onClick={dismissToast}
              className="text-slate-400 hover:text-white text-sm ml-1"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
