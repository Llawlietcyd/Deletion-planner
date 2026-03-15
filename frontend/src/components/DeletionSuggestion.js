import React from 'react';
import { deleteTask } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import { useToast } from './ToastContext';

function DeletionSuggestion({ suggestions, onDismiss, onSuggestionDeleted }) {
  const { t } = useLanguage();
  const { showToast } = useToast();

  const handleAcceptDeletion = async (taskId) => {
    try {
      await deleteTask(taskId);
      if (onSuggestionDeleted) {
        onSuggestionDeleted(taskId);
      }
      if (suggestions.length <= 1 && onDismiss) {
        onDismiss();
      }
    } catch (err) {
      showToast(err.message);
    }
  };

  if (!suggestions || suggestions.length === 0) {
    return null;
  }

  return (
    <section className="card border-[color:var(--accent)]/20 bg-[color:var(--surface)]">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[color:var(--accent)]">
            {t.deleteNowTitle}
          </p>
          <h3 className="mt-1 text-2xl text-[color:var(--text)]">{t.deletionTitle}</h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[color:var(--muted)]">
            {t.deletionIntro} {t.deletionPhilosophy}
          </p>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {suggestions.map((suggestion) => (
          <div
            key={suggestion.id}
            className="rounded-[24px] border border-[color:var(--line)] bg-white/90 p-4 shadow-[0_12px_24px_rgba(0,0,0,0.06)]"
          >
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-base font-semibold text-[color:var(--text)]">{suggestion.title}</p>
                  {suggestion.due_date && (
                    <span className="rounded-full bg-[color:var(--surface)] px-2.5 py-1 text-xs font-semibold text-[color:var(--accent)]">
                      {suggestion.due_date}
                    </span>
                  )}
                </div>

                <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">
                  {suggestion.deletion_reasoning}
                </p>

                {suggestion.trigger_reasons?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {suggestion.trigger_reasons.map((reason) => (
                      <span
                        key={reason}
                        className="rounded-full bg-[color:var(--surface)] px-2.5 py-1 text-xs font-semibold text-[color:var(--accent)]"
                      >
                        {reason}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => handleAcceptDeletion(suggestion.id)}
                  className="rounded-full bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white transition-all hover:opacity-80"
                >
                  {t.deleteBtn}
                </button>
                <button
                  onClick={() => {
                    if (onSuggestionDeleted) {
                      onSuggestionDeleted(suggestion.id);
                    }
                    if (suggestions.length <= 1 && onDismiss) {
                      onDismiss();
                    }
                  }}
                  className="btn-ghost"
                >
                  {t.keepBtn}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default DeletionSuggestion;
