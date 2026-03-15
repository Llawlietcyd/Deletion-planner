import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getAssistantState, sendAssistantMessage } from '../http/api';
import { useLanguage } from '../i18n/LanguageContext';
import { useSession } from './SessionContext';
import { useToast } from './ToastContext';

function ConciergeChatbox() {
  const { lang } = useLanguage();
  const { session } = useSession();
  const { showToast } = useToast();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [state, setState] = useState({
    profile_completed: false,
    profile_summary: '',
    messages: [],
    pending: { type: '', data: {} },
    phase: 'ready',
    status_label: '',
    input_hint: '',
    suggested_prompts: [],
  });
  const [draft, setDraft] = useState('');
  const listRef = useRef(null);
  const textareaRef = useRef(null);

  const copy = useMemo(() => (
    lang === 'zh'
      ? {
          button: '私人管家',
          title: '私人管家',
          subtitleIncomplete: '我负责执行、整理、分析，也可以普通问答；不替你做价值判断。',
          subtitleComplete: '我负责执行、整理、分析，也可以普通问答；不替你做价值判断。',
          placeholder: '比如：我要吃饭；我的生日是什么时候；分析一下最近的专注情况',
          send: '发送',
          thinking: '思考中...',
          empty: '你可以直接让我处理站内事务，或者分析你的专注、完成和情绪模式。',
          error: '我刚刚没有接上，再发一次试试。',
          hints: '快捷指令',
          pendingTitle: '当前需要你补一句',
          enterHint: 'Enter 换行，Cmd/Ctrl + Enter 发送',
        }
      : {
          button: 'Concierge',
          title: 'Private concierge',
          subtitleIncomplete: "I can act inside the app and answer normal questions. I don't make value judgments for you.",
          subtitleComplete: "I can act inside the app and answer normal questions. I don't make value judgments for you.",
          placeholder: 'Try: “I need to eat lunch” or “When is my birthday?”',
          send: 'Send',
          thinking: 'Thinking...',
          empty: 'You can ask me to act inside the app or analyze your focus, completion, and mood patterns.',
          error: 'I missed that. Try sending it once more.',
          hints: 'Quick prompts',
          pendingTitle: 'I need one more thing',
          enterHint: 'Enter for a new line, Cmd/Ctrl + Enter to send',
        }
  ), [lang]);

  const loadState = useCallback(async () => {
    if (!session?.logged_in || !session?.onboarding_completed) {
      return;
    }
    setLoading(true);
    try {
      const data = await getAssistantState(lang);
      setState(data);
    } catch (err) {
      showToast(err.message || 'Failed to load assistant');
    } finally {
      setLoading(false);
    }
  }, [lang, session?.logged_in, session?.onboarding_completed, showToast]);

  useEffect(() => {
    loadState();
  }, [loadState]);

  useEffect(() => {
    if (!open || !listRef.current) {
      return;
    }
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [loading, open, state.messages]);

  useEffect(() => {
    if (!textareaRef.current) {
      return;
    }
    textareaRef.current.style.height = '0px';
    textareaRef.current.style.height = `${Math.min(160, textareaRef.current.scrollHeight)}px`;
  }, [draft]);

  const handleSubmit = useCallback(async (preset) => {
    const message = (preset ?? draft).trim();
    if (!message || loading) {
      return;
    }
    if (!preset) {
      setDraft('');
    }
    setLoading(true);
    try {
      const data = await sendAssistantMessage(message, lang);
      setState(data);
      window.dispatchEvent(new CustomEvent('dp-assistant-updated', { detail: data }));
      if (data.pending?.type) {
        setOpen(true);
      }
    } catch {
      setState((current) => ({
        ...current,
        messages: [
          ...current.messages,
          {
            id: `assistant-error-${Date.now()}`,
            role: 'assistant',
            content: copy.error,
            created_at: new Date().toISOString(),
          },
        ],
      }));
    } finally {
      setLoading(false);
    }
  }, [copy.error, draft, lang, loading]);

  const handleKeyDown = useCallback((event) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  if (!session?.logged_in || !session?.onboarding_completed) {
    return null;
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3">
      {open && (
        <section className="animate-slide-up w-[min(26rem,calc(100vw-2rem))] overflow-hidden rounded-[28px] border border-[color:var(--line)] bg-[rgba(255,250,242,0.96)] shadow-[0_20px_60px_rgba(31,26,23,0.16)] backdrop-blur-xl dark:bg-[rgba(24,29,35,0.96)]">
          <header className="border-b border-[color:var(--line)] px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-[color:var(--accent)]">{copy.title}</p>
                <div className="mt-1 flex items-center gap-2">
                  <h3 className="text-lg text-[color:var(--text)]">{session?.display_name || copy.title}</h3>
                  <span className="rounded-full border border-[color:var(--line)] bg-[color:var(--surface)] px-2.5 py-1 text-[11px] font-medium text-[color:var(--muted)]">
                    {state.status_label || (state.profile_completed ? 'Ready' : 'Setup')}
                  </span>
                </div>
                <p className="mt-2 text-sm text-[color:var(--muted)]">
                  {state.profile_completed ? copy.subtitleComplete : copy.subtitleIncomplete}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-full border border-[color:var(--line)] px-3 py-1 text-xs text-[color:var(--muted)]"
              >
                ×
              </button>
            </div>
          </header>

          <div className="border-b border-[color:var(--line)] px-4 py-3">
            <div className="rounded-[18px] border border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2.5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[color:var(--muted)]">
                {state.pending?.type ? copy.pendingTitle : copy.hints}
              </p>
              <p className="mt-1 text-sm leading-6 text-[color:var(--text)]">
                {state.input_hint || copy.empty}
              </p>
            </div>
          </div>

          <div ref={listRef} className="max-h-[22rem] space-y-3 overflow-y-auto px-4 py-4">
            {state.messages.length === 0 && (
              <div className="rounded-[20px] border border-dashed border-[color:var(--line)] px-4 py-5 text-sm text-[color:var(--muted)]">
                {copy.empty}
              </div>
            )}

            {state.messages.map((message) => (
              <div
                key={message.id}
                className={`max-w-[88%] rounded-[20px] px-4 py-3 text-sm leading-6 ${
                  message.role === 'assistant'
                    ? 'mr-auto border border-[color:var(--line)] bg-[color:var(--surface)] text-[color:var(--text)]'
                    : 'ml-auto bg-[color:var(--accent)] text-white'
                }`}
              >
                <div className="whitespace-pre-wrap">{message.content}</div>
              </div>
            ))}

            {loading && (
              <div className="mr-auto rounded-[20px] border border-[color:var(--line)] bg-[color:var(--surface)] px-4 py-3 text-sm text-[color:var(--muted)]">
                {copy.thinking}
              </div>
            )}
          </div>

          {!!state.suggested_prompts?.length && (
            <div className="border-t border-[color:var(--line)] px-4 py-3">
              <p className="mb-2 text-xs uppercase tracking-[0.22em] text-[color:var(--muted)]">{copy.hints}</p>
              <div className="flex flex-wrap gap-2">
                {state.suggested_prompts.slice(0, 3).map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => handleSubmit(prompt)}
                    className="rounded-full border border-[color:var(--line)] px-3 py-1.5 text-xs text-[color:var(--muted)] transition hover:border-[color:var(--accent)] hover:text-[color:var(--text)]"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          <footer className="border-t border-[color:var(--line)] px-4 py-4">
            <div className="flex items-end gap-3">
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                placeholder={state.input_hint || copy.placeholder}
                className="min-h-[4rem] flex-1 resize-none rounded-[20px] border border-[color:var(--line)] bg-white/70 px-4 py-3 text-sm leading-6 text-[color:var(--text)] outline-none transition focus:border-[color:var(--accent)] dark:bg-white/5"
              />
              <button
                type="button"
                onClick={() => handleSubmit()}
                disabled={loading || !draft.trim()}
                className="btn-primary disabled:cursor-not-allowed disabled:opacity-50"
              >
                {copy.send}
              </button>
            </div>
            <p className="mt-2 text-[11px] text-[color:var(--muted)]">{copy.enterHint}</p>
          </footer>
        </section>
      )}

      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-2 rounded-full border border-[color:var(--line)] bg-[color:var(--surface-strong)] px-4 py-3 text-sm font-semibold text-[color:var(--text)] shadow-[0_10px_28px_rgba(31,26,23,0.14)]"
      >
        <span className={`inline-flex h-2.5 w-2.5 rounded-full ${state.phase === 'pending' ? 'bg-amber-500' : 'bg-[color:var(--accent)]'}`} />
        {copy.button}
      </button>
    </div>
  );
}

export default ConciergeChatbox;
