import React, { useMemo, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { useSession } from './SessionContext';
import BrandMark from './BrandMark';
import LoginLoopMark from './LoginLoopMark';

function parseBirthdayParts(parts, lang) {
  const { year, month, day } = parts;
  if (!year && !month && !day) return { normalized: '', error: '' };
  if (!year || !month || !day) {
    return {
      normalized: '',
      error: lang === 'zh' ? '请把生日补完整。' : 'Please complete your birthday.',
    };
  }

  const y = Number(year);
  const m = Number(month);
  const d = Number(day);
  const date = new Date(Date.UTC(y, m - 1, d));
  const valid =
    date.getUTCFullYear() === y &&
    date.getUTCMonth() + 1 === m &&
    date.getUTCDate() === d;

  if (!valid) {
    return {
      normalized: '',
      error: lang === 'zh' ? '生日日期无效，请重新检查。' : 'Birthday date is invalid.',
    };
  }

  return {
    normalized: `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`,
    error: '',
  };
}

function LoginPage() {
  const { lang, toggleLang, t } = useLanguage();
  const { login } = useSession();
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [birthdayParts, setBirthdayParts] = useState({ year: '', month: '', day: '' });
  const [gender, setGender] = useState('');
  const [showOptional, setShowOptional] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [birthdayError, setBirthdayError] = useState('');
  const currentYear = useMemo(() => new Date().getFullYear(), []);
  const yearOptions = useMemo(
    () => Array.from({ length: 90 }, (_, index) => String(currentYear - index)),
    [currentYear]
  );
  const monthOptions = useMemo(
    () => Array.from({ length: 12 }, (_, index) => String(index + 1)),
    []
  );
  const dayOptions = useMemo(
    () => Array.from({ length: 31 }, (_, index) => String(index + 1)),
    []
  );

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!displayName.trim() || !password.trim()) return;

    const birthdayState = parseBirthdayParts(birthdayParts, lang);
    if (birthdayState.error) {
      setBirthdayError(birthdayState.error);
      return;
    }

    setSubmitting(true);
    setError('');
    setBirthdayError('');
    try {
      await login(
        displayName.trim(),
        password,
        birthdayState.normalized || undefined,
        gender || undefined
      );
    } catch (err) {
      setError(err.message);
    }
    setSubmitting(false);
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-[960px] items-center px-4 py-5">
      <div className="site-shell w-full p-4 md:p-5">
        <section className="animate-slide-up overflow-hidden">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="panel-label">{t.authEyebrow}</div>
              <div className="mt-4">
                <BrandMark
                  size="lg"
                  showWordmark
                  subtitle={
                    lang === 'zh'
                      ? '把任务、情绪、专注和复盘放进同一块真实时间坐标里。'
                      : 'Keep tasks, mood, focus, and review on the same real-world timeline.'
                  }
                />
              </div>
            </div>
            <button onClick={toggleLang} className="btn-ghost !rounded-[18px] !px-4 !py-2 font-[var(--mono)]">
              {lang === 'en' ? '中文' : 'EN'}
            </button>
          </div>

          <div className="mt-5 max-w-[840px]">
            <div className="grid items-start gap-5 md:grid-cols-[minmax(0,1fr)_300px]">
            <div className="max-w-none pt-2 pr-2">
              <div className="panel-label mb-3">{lang === 'zh' ? 'Daily trace system' : 'Daily trace system'}</div>
              <h1 className="max-w-[15ch] text-[clamp(1.14rem,1.7vw,1.58rem)] leading-[1.02] text-[color:var(--text)]">
                {lang === 'zh' ? (
                  '把混乱的一天压成更清楚的一条轨迹。'
                ) : (
                  <>
                    Compress a messy day
                    <br />
                    into a clearer usable trace.
                  </>
                )}
              </h1>
              <p className="mt-3 max-w-[24rem] text-[11px] leading-5 text-[color:var(--muted)]">
                {t.authSubtitle}
              </p>
            </div>
            <div className="pt-2">
              <LoginLoopMark />
            </div>
          </div>
          </div>
          <section className="board-card animate-slide-up mt-5 mx-auto max-w-[760px] p-4 md:p-5">
            <div className="panel-label">{lang === 'zh' ? 'Access Terminal' : 'Access terminal'}</div>
            <h2 className="mt-3 text-[24px] leading-none text-[color:var(--text)]">{t.loginTitle}</h2>
            <p className="mt-3 max-w-[36rem] text-[13px] leading-6 text-[color:var(--muted)]">
              {t.loginSubtitleMultiUser}
            </p>

            <form onSubmit={handleSubmit} className="mt-5 space-y-3.5">
              <label className="block space-y-2 text-sm text-[color:var(--muted)]">
                <span className="panel-label !text-[10px] !tracking-[0.18em] !text-[color:var(--muted)]">{t.loginNameLabel}</span>
                <input
                  type="text"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder={t.loginNamePlaceholder}
                  className="w-full rounded-[18px] border border-[color:var(--line-strong)] bg-white px-4 py-3 text-sm text-[color:var(--text)] outline-none"
                />
              </label>

              <label className="block space-y-2 text-sm text-[color:var(--muted)]">
                <span className="panel-label !text-[10px] !tracking-[0.18em] !text-[color:var(--muted)]">{t.loginPasswordLabel}</span>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={t.loginPasswordPlaceholder}
                  className="w-full rounded-[18px] border border-[color:var(--line-strong)] bg-white px-4 py-3 text-sm text-[color:var(--text)] outline-none"
                />
              </label>

              <button
                type="button"
                onClick={() => setShowOptional((v) => !v)}
                className="panel-label !text-[10px] !tracking-[0.16em] underline underline-offset-4"
              >
                {showOptional ? t.loginHideOptional : t.loginShowOptional}
              </button>

              {showOptional && (
                <div className="board-card space-y-4 p-4">
                  <label className="block space-y-2 text-sm text-[color:var(--muted)]">
                    <span className="panel-label !text-[10px] !tracking-[0.18em] !text-[color:var(--muted)]">{t.loginBirthdayLabel}</span>
                    <div className="grid gap-2 md:grid-cols-3">
                      {(lang === 'en'
                        ? [
                            ['month', monthOptions, 'Month'],
                            ['day', dayOptions, 'Day'],
                            ['year', yearOptions, 'Year'],
                          ]
                        : [
                            ['year', yearOptions, '年'],
                            ['month', monthOptions, '月'],
                            ['day', dayOptions, '日'],
                          ]).map(([key, options, label]) => (
                        <select
                          key={key}
                          value={birthdayParts[key]}
                          onChange={(e) => {
                            setBirthdayParts((current) => ({ ...current, [key]: e.target.value }));
                            if (birthdayError) setBirthdayError('');
                          }}
                          className={`w-full rounded-[18px] border bg-white px-4 py-3 text-sm text-[color:var(--text)] outline-none ${
                            birthdayError ? 'border-[color:var(--danger)]' : 'border-[color:var(--line-strong)]'
                          }`}
                        >
                          <option value="">{label}</option>
                          {options.map((option) => (
                            <option key={option} value={option}>
                              {key === 'year' ? option : option.padStart(2, '0')}
                            </option>
                          ))}
                        </select>
                      ))}
                    </div>
                    {birthdayError && (
                      <p className="text-[12px] leading-5 text-[color:var(--danger)]">{birthdayError}</p>
                    )}
                  </label>
                  <label className="block space-y-2 text-sm text-[color:var(--muted)]">
                    <span className="panel-label !text-[10px] !tracking-[0.18em] !text-[color:var(--muted)]">{t.loginGenderLabel}</span>
                    <select
                      value={gender}
                      onChange={(e) => setGender(e.target.value)}
                      className="w-full rounded-[18px] border border-[color:var(--line-strong)] bg-white px-4 py-3 text-sm text-[color:var(--text)] outline-none"
                    >
                      <option value="">{t.loginGenderPlaceholder}</option>
                      <option value="male">{t.loginGenderMale}</option>
                      <option value="female">{t.loginGenderFemale}</option>
                      <option value="other">{t.loginGenderOther}</option>
                      <option value="prefer_not_to_say">{t.loginGenderPreferNot}</option>
                    </select>
                  </label>
                </div>
              )}

              {error && (
                <div className="rounded-[18px] border border-[color:var(--accent)]/30 bg-[color:var(--surface)] px-4 py-3 text-sm text-[color:var(--accent)]">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={submitting || !displayName.trim() || !password.trim()}
                className="btn-primary w-full disabled:opacity-50"
              >
                {submitting ? t.loginLoading : t.loginAction}
              </button>
            </form>
          </section>
        </section>
      </div>
    </main>
  );
}

export default LoginPage;
