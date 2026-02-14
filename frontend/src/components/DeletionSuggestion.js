import React from 'react';
import { deleteTask } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';

function DeletionSuggestion({ suggestions, onDismiss, onSuggestionDeleted }) {
  const { t } = useLanguage();

  const handleAcceptDeletion = async (taskId) => {
    try {
      await deleteTask(taskId);
      if (onSuggestionDeleted) {
        onSuggestionDeleted(taskId);
      }
      if (suggestions.length <= 1) {
        onDismiss();
      }
    } catch (err) {
      alert(err.message);
    }
  };

  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="card !bg-red-50 !border-red-200">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">🗑️</span>
        <h3 className="font-semibold text-red-800">{t.deletionTitle}</h3>
      </div>
      <p className="text-sm text-red-700 mb-4">
        {t.deletionIntro}
        <span className="font-medium">{t.deletionPhilosophy}</span>
      </p>

      <div className="space-y-3">
        {suggestions.map((s) => (
          <div key={s.id} className="bg-white rounded-lg p-3 border border-red-200">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <p className="font-medium text-slate-800">{s.title}</p>
                <p className="text-sm text-slate-600 mt-1">
                  {s.deletion_reasoning}
                </p>
                {s.trigger_reasons && (
                  <div className="flex gap-2 mt-2 flex-wrap">
                    {s.trigger_reasons.map((r, i) => (
                      <span key={i} className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full">
                        {r}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex gap-1 flex-shrink-0">
                <button
                  onClick={() => handleAcceptDeletion(s.id)}
                  className="text-xs px-3 py-1.5 bg-red-500 text-white rounded-md hover:bg-red-600 font-medium"
                >
                  {t.deleteBtn}
                </button>
                <button
                  onClick={onDismiss}
                  className="text-xs px-3 py-1.5 bg-slate-200 text-slate-600 rounded-md hover:bg-slate-300 font-medium"
                >
                  {t.keepBtn}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default DeletionSuggestion;
