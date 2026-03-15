import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { getSongRecommendations } from '../http/api';

const CANVAS_SIZE = 160;
const CENTER = CANVAS_SIZE / 2;
const TICK_COUNT = 84;
const BASE_RADIUS = 58;
const BASE_TICK_LENGTH = 3.5;
const DEFAULT_BG = {
  shell:
    'radial-gradient(circle at 18% 18%, rgba(124, 156, 255, 0.32), transparent 34%), radial-gradient(circle at 80% 16%, rgba(98, 235, 207, 0.16), transparent 30%), radial-gradient(circle at 50% 110%, rgba(92, 104, 255, 0.22), transparent 44%), linear-gradient(155deg, #171924 0%, #10121a 46%, #090b12 100%)',
  glow: 'rgba(111, 144, 255, 0.2)',
  border: 'rgba(255,255,255,0.08)',
  veil: 'linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.01))',
  coverGlow: 'rgba(111, 144, 255, 0.18)',
  mesh:
    'radial-gradient(150px 110px at 12% 16%, rgba(158, 182, 255, 0.18), transparent 70%), radial-gradient(190px 130px at 85% 14%, rgba(108, 246, 214, 0.12), transparent 70%), radial-gradient(210px 160px at 50% 88%, rgba(104, 123, 255, 0.16), transparent 74%)',
  sheen:
    'linear-gradient(135deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.03) 24%, rgba(255,255,255,0) 48%, rgba(255,255,255,0.06) 72%, rgba(255,255,255,0) 100%)',
  ambient: 'radial-gradient(circle at 50% 0%, rgba(120, 150, 255, 0.16), transparent 52%)',
};
const SONG_CACHE_TTL_MS = 1000 * 60 * 8;
const SONG_CACHE_STORAGE_PREFIX = 'dp_song_cache_v2:';
const songUiCache = new Map();

function readSongUiCache(cacheKey) {
  const inMemoryEntry = songUiCache.get(cacheKey);
  const entry = (() => {
    if (inMemoryEntry) return inMemoryEntry;
    try {
      const stored = window.sessionStorage.getItem(`${SONG_CACHE_STORAGE_PREFIX}${cacheKey}`);
      if (!stored) return null;
      return JSON.parse(stored);
    } catch {
      return null;
    }
  })();
  if (!entry) return null;
  if (entry.expiresAt <= Date.now()) {
    songUiCache.delete(cacheKey);
    try {
      window.sessionStorage.removeItem(`${SONG_CACHE_STORAGE_PREFIX}${cacheKey}`);
    } catch {}
    return null;
  }
  if (!inMemoryEntry) {
    songUiCache.set(cacheKey, entry);
  }
  return entry;
}

function writeSongUiCache(cacheKey, payload) {
  const entry = {
    ...payload,
    expiresAt: Date.now() + SONG_CACHE_TTL_MS,
  };
  songUiCache.set(cacheKey, entry);
  try {
    window.sessionStorage.setItem(`${SONG_CACHE_STORAGE_PREFIX}${cacheKey}`, JSON.stringify(entry));
  } catch {}
}

function rgbToString(rgb, alpha = 1) {
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
}

function lighten(rgb, amount) {
  return {
    r: Math.min(255, Math.round(rgb.r + (255 - rgb.r) * amount)),
    g: Math.min(255, Math.round(rgb.g + (255 - rgb.g) * amount)),
    b: Math.min(255, Math.round(rgb.b + (255 - rgb.b) * amount)),
  };
}

function darken(rgb, amount) {
  return {
    r: Math.max(0, Math.round(rgb.r * (1 - amount))),
    g: Math.max(0, Math.round(rgb.g * (1 - amount))),
    b: Math.max(0, Math.round(rgb.b * (1 - amount))),
  };
}

function saturate(rgb, amount) {
  const avg = (rgb.r + rgb.g + rgb.b) / 3;
  return {
    r: Math.max(0, Math.min(255, Math.round(avg + (rgb.r - avg) * amount))),
    g: Math.max(0, Math.min(255, Math.round(avg + (rgb.g - avg) * amount))),
    b: Math.max(0, Math.min(255, Math.round(avg + (rgb.b - avg) * amount))),
  };
}

function luminance(rgb) {
  return 0.2126 * rgb.r + 0.7152 * rgb.g + 0.0722 * rgb.b;
}

function saturation(rgb) {
  const max = Math.max(rgb.r, rgb.g, rgb.b);
  const min = Math.min(rgb.r, rgb.g, rgb.b);
  return max === 0 ? 0 : (max - min) / max;
}

function colorDistance(a, b) {
  return Math.sqrt((a.r - b.r) ** 2 + (a.g - b.g) ** 2 + (a.b - b.b) ** 2);
}

function chooseAccent(candidates, base) {
  if (!candidates.length) {
    return base;
  }

  return (
    [...candidates]
      .sort((left, right) => {
        const leftScore = saturation(left.rgb) * 220 + colorDistance(left.rgb, base);
        const rightScore = saturation(right.rgb) * 220 + colorDistance(right.rgb, base);
        return rightScore - leftScore;
      })[0]?.rgb || base
  );
}

function chooseHighlight(candidates, base) {
  if (!candidates.length) {
    return lighten(base, 0.22);
  }

  return (
    [...candidates]
      .sort((left, right) => {
        const leftScore = luminance(left.rgb) + saturation(left.rgb) * 80;
        const rightScore = luminance(right.rgb) + saturation(right.rgb) * 80;
        return rightScore - leftScore;
      })[0]?.rgb || lighten(base, 0.22)
  );
}

function extractPaletteFromPixels(pixels) {
  const buckets = new Map();

  for (let i = 0; i < pixels.length; i += 4) {
    const alpha = pixels[i + 3];
    if (alpha < 60) continue;
    const r = pixels[i];
    const g = pixels[i + 1];
    const b = pixels[i + 2];
    const key = `${Math.round(r / 24)}-${Math.round(g / 24)}-${Math.round(b / 24)}`;
    const bucket = buckets.get(key) || { count: 0, r: 0, g: 0, b: 0 };
    bucket.count += 1;
    bucket.r += r;
    bucket.g += g;
    bucket.b += b;
    buckets.set(key, bucket);
  }

  const swatches = [...buckets.values()]
    .map((bucket) => ({
      count: bucket.count,
      rgb: {
        r: Math.round(bucket.r / bucket.count),
        g: Math.round(bucket.g / bucket.count),
        b: Math.round(bucket.b / bucket.count),
      },
    }))
    .filter((swatch) => swatch.count > 1);

  if (!swatches.length) {
    return null;
  }

  const base =
    [...swatches].sort((left, right) => {
      const leftScore = left.count * (1 + saturation(left.rgb) * 0.6);
      const rightScore = right.count * (1 + saturation(right.rgb) * 0.6);
      return rightScore - leftScore;
    })[0]?.rgb || { r: 62, g: 86, b: 144 };

  const accent = chooseAccent(swatches, base);
  const highlight = chooseHighlight(swatches, base);
  const shadow =
    [...swatches].sort((left, right) => luminance(left.rgb) - luminance(right.rgb))[0]?.rgb || darken(base, 0.7);

  return { base, accent, highlight, shadow };
}

function SongRecommendation({ contextSignal = 0 }) {
  const { t, lang } = useLanguage();
  const [songs, setSongs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [refreshIndex, setRefreshIndex] = useState(0);
  const [error, setError] = useState('');
  const [contextMeta, setContextMeta] = useState({ focus_task: '', strategy: '' });
  const [visualPalette, setVisualPalette] = useState(DEFAULT_BG);
  const canvasRef = useRef(null);
  const audioRef = useRef(null);
  const frameRef = useRef(0);
  const requestIdRef = useRef(0);

  const load = useCallback(async () => {
    const cacheKey = `${lang}`;
    const cached = readSongUiCache(cacheKey);
    const shouldForceRefresh = refreshIndex > 0;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    if (cached) {
      setSongs(cached.songs || []);
      setActiveIndex(0);
      setContextMeta({
        focus_task: cached.focus_task || '',
        strategy: cached.strategy || '',
      });
      setError('');
      if (!shouldForceRefresh && cached.contextSignal === contextSignal) {
        setLoading(false);
        return;
      }
    }
    setLoading(!cached);

    try {
      const refreshToken = shouldForceRefresh ? `${Date.now()}-${refreshIndex}` : '';
      const data = await getSongRecommendations(lang, refreshToken);
      if (requestId !== requestIdRef.current) {
        return;
      }
      setError('');
      setSongs(data.songs || []);
      setActiveIndex(0);
      setContextMeta({
        focus_task: data.focus_task || '',
        strategy: data.strategy || '',
      });
      writeSongUiCache(cacheKey, {
        songs: data.songs || [],
        focus_task: data.focus_task || '',
        strategy: data.strategy || '',
        contextSignal,
      });
    } catch {
      if (requestId === requestIdRef.current) {
        if (!cached) {
          setSongs([]);
          setContextMeta({ focus_task: '', strategy: '' });
          setError(t.songError || 'Song recommendations are temporarily unavailable.');
        }
      }
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [contextSignal, lang, refreshIndex, t.songError]);

  useEffect(() => {
    load();
  }, [load, contextSignal]);

  const activeSong = songs[activeIndex] || songs[0] || null;
  const queue = useMemo(() => songs.slice(0, 4), [songs]);

  useEffect(() => {
    if (!activeSong?.cover_url) {
      setVisualPalette(DEFAULT_BG);
      return undefined;
    }

    let cancelled = false;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.referrerPolicy = 'no-referrer';
    img.onload = () => {
      try {
        const swatch = document.createElement('canvas');
        swatch.width = 24;
        swatch.height = 24;
        const swatchCtx = swatch.getContext('2d');
        if (!swatchCtx) {
          setVisualPalette({
            shell: `linear-gradient(180deg, rgba(10,10,12,0.78), rgba(10,10,12,0.96)), url(${activeSong.cover_url}) center/cover`,
            glow: 'rgba(255,255,255,0.14)',
          });
          return;
        }
        swatchCtx.drawImage(img, 0, 0, swatch.width, swatch.height);
        const pixels = swatchCtx.getImageData(0, 0, swatch.width, swatch.height).data;
        let total = 0;
        let r = 0;
        let g = 0;
        let b = 0;
        for (let i = 0; i < pixels.length; i += 4) {
          const alpha = pixels[i + 3];
          if (alpha < 40) continue;
          r += pixels[i];
          g += pixels[i + 1];
          b += pixels[i + 2];
          total += 1;
        }
        if (!total) {
          return;
        }
        const palette =
          extractPaletteFromPixels(pixels) || {
            base: { r: Math.round(r / total), g: Math.round(g / total), b: Math.round(b / total) },
            accent: { r: Math.round(r / total), g: Math.round(g / total), b: Math.round(b / total) },
            highlight: lighten({ r: Math.round(r / total), g: Math.round(g / total), b: Math.round(b / total) }, 0.18),
            shadow: darken({ r: Math.round(r / total), g: Math.round(g / total), b: Math.round(b / total) }, 0.72),
          };
        const base = saturate(palette.base, 1.12);
        const accent = saturate(lighten(palette.accent, 0.06), 1.28);
        const highlight = lighten(saturate(palette.highlight, 1.18), 0.12);
        const shadow = darken(saturate(palette.shadow, 1.06), 0.58);
        const deep = darken(base, 0.74);
        const deeper = darken(shadow, 0.54);
        if (!cancelled) {
          const ink = darken(shadow, 0.76);
          setVisualPalette({
            shell: `radial-gradient(circle at 16% 18%, ${rgbToString(highlight, 0.34)}, transparent 32%), radial-gradient(circle at 82% 16%, ${rgbToString(accent, 0.28)}, transparent 30%), radial-gradient(circle at 54% 104%, ${rgbToString(base, 0.34)}, transparent 44%), linear-gradient(160deg, ${rgbToString(deep, 0.96)} 0%, ${rgbToString(shadow, 0.94)} 42%, ${rgbToString(deeper, 0.98)} 100%)`,
            glow: rgbToString(accent, 0.2),
            border: rgbToString(highlight, 0.11),
            veil: `linear-gradient(180deg, ${rgbToString(highlight, 0.06)}, ${rgbToString(base, 0.012)})`,
            coverGlow: rgbToString(accent, 0.18),
            mesh: `radial-gradient(150px 110px at 14% 16%, ${rgbToString(highlight, 0.2)}, transparent 72%), radial-gradient(190px 130px at 84% 14%, ${rgbToString(accent, 0.16)}, transparent 70%), radial-gradient(220px 170px at 52% 90%, ${rgbToString(base, 0.18)}, transparent 74%), conic-gradient(from 220deg at 50% 50%, ${rgbToString(ink, 0)} 0deg, ${rgbToString(accent, 0.12)} 74deg, ${rgbToString(highlight, 0.08)} 150deg, ${rgbToString(base, 0.12)} 232deg, ${rgbToString(ink, 0)} 320deg, ${rgbToString(ink, 0)} 360deg)`,
            sheen: `linear-gradient(135deg, ${rgbToString(highlight, 0.13)} 0%, ${rgbToString(highlight, 0.035)} 22%, rgba(255,255,255,0) 46%, ${rgbToString(accent, 0.07)} 72%, rgba(255,255,255,0) 100%)`,
            ambient: `radial-gradient(circle at 50% 0%, ${rgbToString(accent, 0.16)}, transparent 52%)`,
          });
        }
      } catch {
        if (!cancelled) {
          setVisualPalette({
            shell: `radial-gradient(circle at top, rgba(255,255,255,0.18), transparent 30%), linear-gradient(160deg, rgba(10,10,12,0.84), rgba(8,8,12,0.98))`,
            glow: 'rgba(255,255,255,0.14)',
            border: 'rgba(255,255,255,0.08)',
            veil: 'linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.01))',
            coverGlow: 'rgba(255,255,255,0.14)',
            mesh:
              'radial-gradient(150px 110px at 12% 16%, rgba(255,255,255,0.12), transparent 70%), radial-gradient(190px 130px at 85% 14%, rgba(255,255,255,0.08), transparent 70%)',
            sheen:
              'linear-gradient(135deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.04) 22%, rgba(255,255,255,0) 48%, rgba(255,255,255,0.05) 76%, rgba(255,255,255,0) 100%)',
            ambient: 'radial-gradient(circle at 50% 0%, rgba(255,255,255,0.12), transparent 52%)',
          });
        }
      }
    };
    img.onerror = () => {
      if (!cancelled) {
        setVisualPalette(DEFAULT_BG);
      }
    };
    img.src = activeSong.cover_url;
    return () => {
      cancelled = true;
    };
  }, [activeSong?.cover_url]);

  useEffect(() => {
    setIsPlaying(false);
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.load();
    }
  }, [activeIndex, songs]);

  const togglePreview = async () => {
    if (!audioRef.current || !activeSong?.preview_url) {
      return;
    }
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
      return;
    }
    try {
      await audioRef.current.play();
      setIsPlaying(true);
    } catch {
      setIsPlaying(false);
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return undefined;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      return undefined;
    }

    let lastFrame = 0;
    const targetDelta = isPlaying ? 1000 / 30 : 1000 / 12;

    const draw = (now) => {
      if (document.hidden) {
        frameRef.current = window.requestAnimationFrame(draw);
        return;
      }
      if (now - lastFrame < targetDelta) {
        frameRef.current = window.requestAnimationFrame(draw);
        return;
      }
      lastFrame = now;
      const time = now * 0.0022;
      ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

      ctx.save();
      ctx.translate(CENTER, CENTER);

      ctx.beginPath();
      ctx.arc(0, 0, 50, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255,255,255,0.14)';
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.beginPath();
      ctx.setLineDash([3, 4]);
      ctx.arc(0, 0, 66, 0, Math.PI * 2);
      ctx.strokeStyle = isPlaying ? 'rgba(255,255,255,0.28)' : 'rgba(142,146,153,0.34)';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);

      for (let i = 0; i < TICK_COUNT; i += 1) {
        const angle = (i / TICK_COUNT) * Math.PI * 2;
        const motion = isPlaying
          ? Math.max(
              0,
              Math.sin(angle * 5 + time * 1.8) * 10 +
                Math.cos(angle * 11 - time * 2.6) * 8 +
                (Math.sin(time * 3.3 + i * 0.25) + 1) * 5
            )
          : Math.max(
              0,
              Math.sin(i * 0.16 + time * 1.05) * 3.6 +
                Math.cos(i * 0.28 - time * 0.92) * 2.2 +
                (Math.sin(time * 0.9 + i * 0.05) + 1) * 0.9
            );
        const tickLength = BASE_TICK_LENGTH + motion;

        ctx.save();
        ctx.rotate(angle);
        ctx.beginPath();
        ctx.moveTo(0, -BASE_RADIUS);
        ctx.lineTo(0, -BASE_RADIUS - tickLength);
        ctx.strokeStyle = isPlaying ? 'rgba(255,255,255,0.92)' : 'rgba(162,166,173,0.82)';
        ctx.lineWidth = isPlaying ? 1.45 : 1.35;
        ctx.stroke();
        ctx.restore();
      }

      ctx.restore();
      frameRef.current = window.requestAnimationFrame(draw);
    };

    frameRef.current = window.requestAnimationFrame(draw);
    return () => {
      window.cancelAnimationFrame(frameRef.current);
    };
  }, [isPlaying]);

  return (
    <section
      className="relative isolate overflow-hidden rounded-[14px] border text-white shadow-[0_14px_32px_rgba(0,0,0,0.18)] transition-[background,border-color,box-shadow] duration-500"
      style={{
        background: visualPalette.shell,
        boxShadow: `0 14px 32px ${visualPalette.glow}`,
        borderColor: visualPalette.border,
      }}
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: visualPalette.veil }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-95"
        style={{ background: visualPalette.mesh, mixBlendMode: 'screen' }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-90"
        style={{ background: visualPalette.sheen }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-85 blur-[26px]"
        style={{ background: visualPalette.ambient }}
      />
      {activeSong?.cover_url ? (
        <div
          className="pointer-events-none absolute inset-x-[-12%] top-[-10%] h-[52%] opacity-45 blur-[28px]"
          style={{
            backgroundImage: `linear-gradient(180deg, rgba(8, 8, 12, 0.08), rgba(8, 8, 12, 0.48)), url(${activeSong.cover_url})`,
            backgroundPosition: 'center',
            backgroundSize: 'cover',
            filter: 'saturate(1.2) blur(30px)',
            transform: 'scale(1.18)',
          }}
        />
      ) : null}
      <div
        className="pointer-events-none absolute inset-x-4 top-4 h-24 rounded-[22px] blur-2xl"
        style={{ background: `radial-gradient(circle at center, ${visualPalette.coverGlow}, transparent 72%)` }}
      />
      <div className="flex items-start justify-between px-3 pb-1.5 pt-3">
        <span className="font-mono text-[9px] tracking-[0.18em] text-white/45">W - 02</span>
        <span className="font-mono text-[9px] tracking-[0.18em] text-white/45">AUDIO_OUT</span>
      </div>

      <div className="relative z-10 space-y-3 px-3 pb-3">
        <div className="grid grid-cols-[70px_minmax(0,1fr)_34px] gap-2.5">
          <div className="h-[70px] w-[70px] overflow-hidden rounded-[14px] border border-white/10 bg-white/6 shadow-[0_12px_24px_rgba(0,0,0,0.28)]">
            {activeSong?.cover_url ? (
              <img
                src={activeSong.cover_url}
                alt={`${activeSong.album || activeSong.name} cover`}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-xl text-white/45">♪</div>
            )}
          </div>

          <div className="min-w-0 pt-0.5">
            <p className="font-mono text-[8px] uppercase tracking-[0.18em] text-white/40">{t.songStatus}</p>
            {loading ? (
              <p className="mt-1 text-[11px] text-white/55">{t.songLoading}</p>
            ) : error ? (
              <p className="mt-1 text-[11px] text-[#ffb1a8]">{error}</p>
            ) : activeSong ? (
              <>
                <p className="mt-1 max-h-8 overflow-hidden text-[12px] leading-4 text-white">{activeSong.name}</p>
                <p className="mt-0.5 truncate text-[10px] text-white/55">{activeSong.artist}</p>
                <p className="mt-1 truncate font-mono text-[8px] uppercase tracking-[0.15em] text-white/38">
                  {activeSong.album || t.songUnknownAlbum}
                </p>
                {contextMeta.focus_task ? (
                  <p className="mt-1 truncate text-[9px] text-white/42">{contextMeta.focus_task}</p>
                ) : null}
              </>
            ) : (
              <p className="mt-1 text-[11px] text-white/45">{t.songEmpty}</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <button
              onClick={() => setRefreshIndex((value) => value + 1)}
              className="flex h-[34px] w-[34px] items-center justify-center rounded-full border border-white/16 bg-white/[0.03] font-mono text-[8px] text-white/70 transition hover:border-white/40 hover:bg-white/[0.06]"
              aria-label={t.songRefresh}
            >
              ↺
            </button>
          </div>
        </div>

        <div className="relative flex min-h-[132px] items-center justify-center">
          <div className="relative flex h-[160px] w-[160px] items-center justify-center">
            <div className={`absolute h-[122px] w-[122px] rounded-full border border-dashed border-white/25 ${isPlaying ? 'animate-[spin_36s_linear_infinite]' : ''}`} />

            <canvas
              ref={canvasRef}
              width={CANVAS_SIZE}
              height={CANVAS_SIZE}
              className="absolute inset-0 h-full w-full"
            />

            <div className="pointer-events-none absolute inset-0">
              <div
                className={`absolute left-1/2 top-1/2 h-[42px] w-[42px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/15 ${isPlaying ? 'animate-[pulse-ring_1.8s_infinite_cubic-bezier(0.215,0.61,0.355,1)]' : 'opacity-0'}`}
              />
            </div>

            <button
              onClick={togglePreview}
              disabled={!activeSong?.preview_url}
              className="relative z-10 flex h-[42px] w-[42px] items-center justify-center rounded-full border border-white/18 bg-black/28 transition hover:scale-105 hover:border-white/45 disabled:cursor-not-allowed disabled:opacity-35"
              aria-label={isPlaying ? t.songPausePreview : t.songPlayPreview}
            >
              <div
                className={
                  isPlaying
                    ? 'h-[10px] w-[10px] rounded-[2px] bg-[#ff4d5b] shadow-[0_0_12px_rgba(255,77,91,0.55)]'
                    : 'ml-[2px] h-0 w-0 border-b-[6px] border-l-[10px] border-t-[6px] border-b-transparent border-l-white border-t-transparent'
                }
              />
            </button>

            <audio
              ref={audioRef}
              src={activeSong?.preview_url || ''}
              onEnded={() => setIsPlaying(false)}
              onPause={() => setIsPlaying(false)}
            />
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={togglePreview}
            disabled={!activeSong?.preview_url}
            className="rounded-full border border-white/14 px-3 py-1.5 font-mono text-[8px] uppercase tracking-[0.16em] text-white/74 transition hover:border-white/35 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
          >
            {isPlaying ? t.songPausePreview : t.songPlayPreview}
          </button>
          {activeSong?.spotify_url ? (
            <a
              href={activeSong.spotify_url}
              target="_blank"
              rel="noreferrer"
              className="flex-1 rounded-full border border-white/14 px-3 py-1.5 text-center font-mono text-[8px] uppercase tracking-[0.16em] text-white/68 transition hover:border-white/35 hover:text-white"
            >
              {t.songOpenSpotify}
            </a>
          ) : (
            <span className="flex-1 rounded-full border border-white/8 px-3 py-1.5 text-center font-mono text-[8px] uppercase tracking-[0.16em] text-white/30 cursor-not-allowed">
              {t.songOpenSpotify}
            </span>
          )}
        </div>

        {queue.length > 1 ? (
          <div className="space-y-1.5 border-t border-white/8 pt-2.5">
            {queue.map((song, index) => (
              <button
                key={`${song.name}-${index}`}
                onClick={() => setActiveIndex(index)}
                className={`flex w-full items-center gap-2 rounded-[10px] px-2 py-1.5 text-left transition ${
                  index === activeIndex ? 'bg-white/10' : 'bg-white/[0.03] hover:bg-white/[0.06]'
                }`}
              >
                <div className="h-8 w-8 overflow-hidden rounded-[9px] bg-white/8">
                  {song.cover_url ? (
                    <img src={song.cover_url} alt={`${song.album || song.name} cover`} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-white/45">♪</div>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[10px] text-white">{song.name}</p>
                  <p className="truncate text-[9px] text-white/45">{song.artist}</p>
                </div>
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <style>{`
        @keyframes pulse-ring {
          0% { transform: translate(-50%, -50%) scale(0.72); opacity: 0; }
          45% { opacity: 0.34; }
          100% { transform: translate(-50%, -50%) scale(1.8); opacity: 0; }
        }
      `}</style>
    </section>
  );
}

export default SongRecommendation;
