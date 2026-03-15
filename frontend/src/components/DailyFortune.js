import React, { useCallback, useEffect, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { getDailyFortune, getTodayFortune } from '../http/api';
import TarotCardArt from './TarotCardArt';
import fusionPixelLatin from '../assets/fonts/fusion-pixel-12px-monospaced-latin.ttf.woff2';
import fusionPixelZhHans from '../assets/fonts/fusion-pixel-12px-monospaced-zh_hans.ttf.woff2';

function DailyFortune() {
  const { t, lang } = useLanguage();
  const [fortune, setFortune] = useState(null);
  const [loading, setLoading] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [checkedOnce, setCheckedOnce] = useState(false);

  const generate = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getDailyFortune(lang);
      setFortune(data);
      setRevealed(true);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [lang]);

  const checkExisting = useCallback(async () => {
    try {
      const data = await getTodayFortune(lang);
      if (data?.generated) {
        setFortune(data);
        setRevealed(true);
      }
    } catch {
      // ignore
    }
  }, [lang]);

  useEffect(() => {
    setFortune(null);
    setRevealed(false);
    setCheckedOnce(false);
  }, [lang]);

  useEffect(() => {
    if (!expanded || checkedOnce) {
      return;
    }
    setCheckedOnce(true);
    checkExisting();
  }, [expanded, checkedOnce, checkExisting]);

  return (
    <section className="card fortune-shell">
      <div className="fortune-grid relative z-10">
        <button
          onClick={() => setExpanded((value) => !value)}
          className="col-span-full flex w-full items-start justify-between text-left"
        >
          <div>
            <p className="fortune-kicker">ORACLE // DAILY READOUT</p>
            <h2 className="mt-3 text-2xl text-[#ffd36a]">{t.fortuneTitle}</h2>
            <p className="mt-2 fortune-copy text-sm text-[#cdbf9c]">{t.fortuneSubtitle}</p>
          </div>
          <span className="mt-1 text-lg text-[#ffbf3c]/82">{expanded ? '▾' : '▸'}</span>
        </button>

        {expanded ? (
          !revealed ? (
            <div className="col-span-full flex flex-col items-center gap-4 py-8">
              <div className="fortune-sealed-card flex h-28 w-20 items-center justify-center text-3xl text-[#ffcf69]">
                ?
              </div>
              <button onClick={generate} disabled={loading} className="btn-primary">
                {loading ? (t.fortuneLoading || 'Revealing...') : (t.fortuneReveal || "Reveal today's card")}
              </button>
            </div>
          ) : fortune ? (
            <>
              <div className="fortune-panel fortune-panel-card">
                <TarotCardArt fortune={fortune} />
              </div>

              <div className="fortune-panel fortune-panel-main">
                <div className="fortune-panel-head">
                  <span>IDENT</span>
                  <span className="fortune-dim">{fortune.visual_theme || 'SIGNAL'}</span>
                </div>
                <p className="fortune-metadata">{fortune.zodiac_label || t.fortuneNoBirthday}</p>
                <h3 className="mt-3 fortune-title">{fortune.card}</h3>
                <p className="mt-4 fortune-copy fortune-interpretation">{fortune.interpretation}</p>

                {fortune.focus_task ? (
                  <div className="mt-5 fortune-inline-block">
                    <p className="fortune-inline-label">{t.fortuneFocusTask}</p>
                    <p className="fortune-copy mt-2 text-sm text-[#efe3c8]">{fortune.focus_task}</p>
                  </div>
                ) : null}

                {(fortune.planned_tasks || []).length > 0 ? (
                  <div className="mt-4 fortune-inline-block">
                    <p className="fortune-inline-label">{t.fortunePlanSignal}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {fortune.planned_tasks.map((task, index) => (
                        <span key={`${task}-${index}`} className="fortune-chip">
                          {task}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="fortune-panel">
                <div className="fortune-panel-head">
                  <span>{t.fortuneAuspicious}</span>
                  <span className="fortune-dim">POSITIVE</span>
                </div>
                <ul className="mt-3 space-y-2">
                  {(fortune.auspicious || []).map((item, index) => (
                    <li key={index} className="fortune-copy text-sm text-[#efe3c8]">+ {item}</li>
                  ))}
                </ul>
              </div>

              <div className="fortune-panel">
                <div className="fortune-panel-head">
                  <span>{t.fortuneInauspicious}</span>
                  <span className="fortune-dim">NEGATIVE</span>
                </div>
                <ul className="mt-3 space-y-2">
                  {(fortune.inauspicious || []).map((item, index) => (
                    <li key={index} className="fortune-copy text-sm text-[#d8c19a]">- {item}</li>
                  ))}
                </ul>
              </div>

              <div className="fortune-panel col-span-full">
                <div className="fortune-panel-head">
                  <span>AUX</span>
                  <span className="fortune-dim">GUIDANCE</span>
                </div>
                <p className="mt-3 fortune-copy text-sm text-[#d7c59f]">
                  {t.fortuneLuckyColor}: <span className="text-[#ffcf69]">{fortune.lucky_color}</span>
                </p>
                <p className="mt-3 fortune-copy text-base italic text-[#f0e4ca]">
                  {t.fortuneAdvice}: {fortune.advice}
                </p>
              </div>
            </>
          ) : null
        ) : null}
      </div>

      <style>{`
        @font-face {
          font-family: 'Fusion Pixel';
          src: url(${fusionPixelLatin}) format('woff2');
          unicode-range: U+0000-00FF, U+2000-206F;
        }
        @font-face {
          font-family: 'Fusion Pixel';
          src: url(${fusionPixelZhHans}) format('woff2');
          unicode-range: U+3000-303F, U+4E00-9FFF, U+FF00-FFEF;
        }

        .fortune-shell {
          position: relative;
          overflow: hidden;
          border-radius: 10px;
          border: 1px solid rgba(255, 191, 60, 0.18);
          background:
            radial-gradient(circle at top left, rgba(255, 191, 60, 0.08), transparent 28%),
            linear-gradient(180deg, #090b10, #020305 88%);
          box-shadow: inset 0 0 80px rgba(0, 0, 0, 0.78), 0 24px 60px rgba(0, 0, 0, 0.22);
        }
        .fortune-shell::before {
          content: '';
          position: absolute;
          inset: 0;
          pointer-events: none;
          background:
            linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.12) 50%),
            radial-gradient(circle at 72% 26%, rgba(255, 191, 60, 0.08), transparent 14%),
            url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='720' height='720' viewBox='0 0 720 720' shape-rendering='geometricPrecision'%3E%3Cg fill='none' stroke='rgba(255,191,60,0.11)' stroke-width='2'%3E%3Cpolygon points='360,92 504,342 216,342'/%3E%3Cpolygon points='360,628 504,378 216,378'/%3E%3Crect x='222' y='222' width='276' height='276' rx='0'/%3E%3Crect x='308' y='308' width='104' height='104' rx='0'/%3E%3Cline x1='360' y1='54' x2='360' y2='666'/%3E%3Cline x1='54' y1='360' x2='666' y2='360'/%3E%3C/g%3E%3C/svg%3E");
          background-size: 100% 4px, 100% 100%, 110% auto;
          background-position: 0 0, 0 0, center;
          background-repeat: repeat, no-repeat, no-repeat;
          opacity: 0.5;
        }
        .fortune-grid {
          display: grid;
          grid-template-columns: 260px minmax(0, 1fr);
          gap: 18px;
          padding: 22px;
        }
        .fortune-kicker,
        .fortune-panel-head,
        .fortune-inline-label {
          font-family: 'Fusion Pixel', monospace;
          letter-spacing: 0.16em;
          text-transform: uppercase;
          color: #ffbf3c;
          text-shadow: 0 0 6px rgba(255, 191, 60, 0.16);
        }
        .fortune-panel-head {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
        }
        .fortune-dim {
          color: #8f7850;
        }
        .fortune-title {
          font-family: 'Fusion Pixel', monospace;
          font-size: 30px;
          line-height: 1.2;
          color: #ffd36a;
          text-shadow: 0 0 8px rgba(255, 191, 60, 0.14);
        }
        .fortune-copy {
          font-family: 'Fusion Pixel', monospace;
          line-height: 2;
          letter-spacing: 0.02em;
          text-shadow: 0 0 4px rgba(255, 191, 60, 0.08);
        }
        .fortune-metadata {
          font-family: 'Fusion Pixel', monospace;
          font-size: 13px;
          color: #b69b69;
          letter-spacing: 0.04em;
        }
        .fortune-interpretation {
          font-size: 18px;
          color: #f0e4ca;
        }
        .fortune-panel {
          position: relative;
          border: 1px solid rgba(255, 191, 60, 0.22);
          background: rgba(255, 191, 60, 0.02);
          padding: 16px 18px;
          min-width: 0;
        }
        .fortune-panel-card {
          display: flex;
          align-items: flex-start;
          justify-content: center;
          background: rgba(255, 191, 60, 0.015);
        }
        .fortune-panel-main {
          min-height: 100%;
        }
        .fortune-inline-block {
          border-top: 1px dashed rgba(255, 191, 60, 0.2);
          padding-top: 14px;
        }
        .fortune-chip {
          border: 1px solid rgba(255, 191, 60, 0.22);
          padding: 6px 10px;
          font-family: 'Fusion Pixel', monospace;
          font-size: 12px;
          color: #e6d4ae;
          background: rgba(255, 191, 60, 0.04);
        }
        .fortune-sealed-card {
          border: 1px solid rgba(255, 191, 60, 0.26);
          background:
            radial-gradient(circle at 50% 24%, rgba(255,191,60,0.12), transparent 28%),
            linear-gradient(180deg, rgba(10, 8, 4, 0.98), rgba(5, 4, 1, 0.98));
        }
        @media (max-width: 900px) {
          .fortune-grid {
            grid-template-columns: 1fr;
          }
          .fortune-panel-card {
            justify-content: flex-start;
          }
        }
      `}</style>
    </section>
  );
}

export default DailyFortune;
