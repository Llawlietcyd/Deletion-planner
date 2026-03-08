import React, { useCallback, useEffect, useState } from 'react';
import { checkHealth, getLLMConfig, testLLMConnection, updateLLMConfig } from '../http/api';
import { useDarkMode } from '../i18n/DarkModeContext';
import { useLanguage } from '../i18n/LanguageContext';

function SettingsPage() {
  const { lang, toggleLang, t } = useLanguage();
  const { isDark, toggleDark } = useDarkMode();
  const [health, setHealth] = useState('');
  const [llmProvider, setLlmProvider] = useState('mock');
  const [llmApiKey, setLlmApiKey] = useState('');
  const [llmModel, setLlmModel] = useState('');
  const [llmKeyMasked, setLlmKeyMasked] = useState('');
  const [llmKeyIsSet, setLlmKeyIsSet] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function loadHealth() {
      try {
        const response = await checkHealth();
        if (mounted) {
          setHealth(response.ok ? t.backendHealthy : t.backendUnhealthy);
        }
      } catch {
        if (mounted) {
          setHealth(t.backendUnhealthy);
        }
      }
    }

    loadHealth();
    return () => {
      mounted = false;
    };
  }, [t]);

  const loadLLMConfig = useCallback(async () => {
    try {
      const config = await getLLMConfig();
      setLlmProvider(config.provider || 'mock');
      setLlmModel(config.model || '');
      setLlmKeyIsSet(config.api_key_set || false);
      setLlmKeyMasked(config.api_key_masked || '');
      setLlmApiKey('');
    } catch {
      // Ignore settings load failures here.
    }
  }, []);

  useEffect(() => {
    loadLLMConfig();
  }, [loadLLMConfig]);

  const handleSaveConfig = async () => {
    setSaving(true);
    setSaveMsg('');
    setTestResult(null);
    try {
      const payload = { provider: llmProvider };
      if (llmApiKey.trim()) {
        payload.api_key = llmApiKey.trim();
      }
      if (llmModel.trim()) {
        payload.model = llmModel.trim();
      }
      await updateLLMConfig(payload);
      setSaveMsg(t.aiSaved);
      await loadLLMConfig();
      setTimeout(() => setSaveMsg(''), 2000);
    } catch (err) {
      setSaveMsg(err.message);
    }
    setSaving(false);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testLLMConnection();
      setTestResult(result);
    } catch (err) {
      setTestResult({ ok: false, message: err.message });
    }
    setTesting(false);
  };

  const defaultModels = {
    mock: '',
    openai: 'gpt-4o-mini',
    claude: 'claude-sonnet-4-20250514',
    deepseek: 'deepseek-chat',
  };

  return (
    <div className="space-y-6">
      <section className="card">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[color:var(--muted)]">
          System controls
        </p>
        <h1 className="mt-2 text-3xl text-[color:var(--text)]">{t.settingsTitle}</h1>
        <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">{t.settingsSubtitle}</p>
      </section>

      <section className="card space-y-5">
        <div>
          <h2 className="text-2xl text-[color:var(--text)]">{t.aiConfigTitle}</h2>
          <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">{t.aiConfigSubtitle}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {[
            { value: 'mock', label: t.aiProviderMock },
            { value: 'openai', label: t.aiProviderOpenAI },
            { value: 'claude', label: t.aiProviderClaude },
            { value: 'deepseek', label: t.aiProviderDeepSeek },
          ].map((option) => (
            <button
              key={option.value}
              onClick={() => {
                setLlmProvider(option.value);
                setTestResult(null);
                setSaveMsg('');
                if (!llmModel || Object.values(defaultModels).includes(llmModel)) {
                  setLlmModel(defaultModels[option.value] || '');
                }
              }}
              className={`rounded-full px-4 py-2 text-sm transition-all ${
                llmProvider === option.value
                  ? 'bg-[color:var(--accent-soft)] text-[color:var(--accent)]'
                  : 'bg-white/70 text-[color:var(--muted)]'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>

        {llmProvider === 'mock' && (
          <div className="rounded-[22px] border border-[color:var(--line)] bg-[color:var(--bg-strong)] p-4 text-sm leading-6 text-[color:var(--muted)]">
            {t.aiMockNote}
          </div>
        )}

        {llmProvider !== 'mock' && (
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm text-[color:var(--muted)]">
              <span>{t.aiApiKey}</span>
              <input
                type="password"
                value={llmApiKey}
                onChange={(event) => setLlmApiKey(event.target.value)}
                placeholder={llmKeyIsSet ? '(leave blank to keep existing key)' : t.aiApiKeyPlaceholder}
                className="w-full rounded-[20px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none"
              />
              <span className="block text-xs">
                {llmKeyIsSet ? `${t.aiApiKeySet} (${llmKeyMasked})` : t.aiApiKeyNotSet}
              </span>
            </label>

            <label className="space-y-2 text-sm text-[color:var(--muted)]">
              <span>{t.aiModel}</span>
              <input
                type="text"
                value={llmModel}
                onChange={(event) => setLlmModel(event.target.value)}
                placeholder={t.aiModelPlaceholder}
                className="w-full rounded-[20px] border border-[color:var(--line)] bg-white/80 px-4 py-3 text-sm text-[color:var(--text)] outline-none"
              />
            </label>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <button onClick={handleSaveConfig} disabled={saving} className="btn-primary disabled:opacity-50">
            {saving ? t.aiSaving : t.aiSaveConfig}
          </button>
          <button onClick={handleTestConnection} disabled={testing || saving} className="btn-ghost disabled:opacity-50">
            {testing ? t.aiTesting : t.aiTestConnection}
          </button>
          {saveMsg && <span className="text-sm text-[color:var(--accent)]">{saveMsg}</span>}
        </div>

        {testResult && (
          <div
            className={`rounded-[22px] border px-4 py-3 text-sm ${
              testResult.ok
                ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                : 'border-red-200 bg-red-50 text-red-800'
            }`}
          >
            <p className="font-semibold">{testResult.ok ? t.aiTestSuccess : t.aiTestFailed}</p>
            {testResult.message && <p className="mt-1">{testResult.message}</p>}
          </div>
        )}
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="card">
          <h2 className="text-2xl text-[color:var(--text)]">{t.appearance}</h2>
          <div className="mt-4 flex items-center justify-between">
            <div>
              <p className="text-sm text-[color:var(--text)]">{t.darkMode}</p>
              <p className="mt-1 text-xs text-[color:var(--muted)]">{isDark ? t.darkModeOn : t.darkModeOff}</p>
            </div>
            <button
              onClick={toggleDark}
              className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
                isDark ? 'bg-[color:var(--accent)]' : 'bg-slate-300'
              }`}
            >
              <span
                className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                  isDark ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>

        <div className="card">
          <h2 className="text-2xl text-[color:var(--text)]">{t.languageSetting}</h2>
          <div className="mt-4 flex items-center justify-between gap-3">
            <p className="text-sm text-[color:var(--muted)]">
              {lang === 'en' ? t.languageEnglish : t.languageChinese}
            </p>
            <button onClick={toggleLang} className="btn-primary">
              {t.switchLanguage}
            </button>
          </div>
        </div>
      </section>

      <section className="card">
        <h2 className="text-2xl text-[color:var(--text)]">{t.systemStatus}</h2>
        <p className="mt-3 text-sm text-[color:var(--muted)]">{health}</p>
      </section>
    </div>
  );
}

export default SettingsPage;
