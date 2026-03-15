import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';

const PIXEL_BORDER = '#433528';
const SPRITE_SIZE = 10;

const SPRITE_DEFS = [
  {
    name: 'ice-cream',
    palette: { a: '#d4a055', b: '#f06292', c: '#f8bbd0', d: '#8b5e3c', e: '#fce4ec' },
    sprite: [
      '..........',
      '...bbb....',
      '..beceb...',
      '..beeeb...',
      '...bbb....',
      '...dad....',
      '..dadad...',
      '...dad....',
      '....d.....',
      '..........',
    ],
  },
  {
    name: 'cola',
    palette: { a: '#b0bec5', b: '#c62828', c: '#ef5350', d: '#ffffff', e: '#e53935' },
    sprite: [
      '..........',
      '...aaaa...',
      '..abbbba..',
      '..abccba..',
      '..abddba..',
      '..abddba..',
      '..abccba..',
      '..abccba..',
      '..abbbba..',
      '..........',
    ],
  },
  {
    name: 'apple',
    palette: { a: '#5d4037', b: '#e53935', c: '#ef9a9a', d: '#2e7d32', e: '#c62828' },
    sprite: [
      '....da....',
      '...daa....',
      '..bbbbb...',
      '.bbcccbb..',
      '.bbcccbb..',
      '.bbbbbbb..',
      '.bbeebbb..',
      '..bbbbb...',
      '..........',
      '..........',
    ],
  },
  {
    name: 'car',
    palette: { a: '#263238', b: '#1e88e5', c: '#90caf9', d: '#ffd54f', e: '#757575' },
    sprite: [
      '..........',
      '..........',
      '...bbbb...',
      '..bccccb..',
      '.bbbbbbbb.',
      'dbbbbbbbbd',
      '..ae..ae..',
      '..aa..aa..',
      '..........',
      '..........',
    ],
  },
  {
    name: 'donut',
    palette: { a: '#6d4c41', b: '#f06292', c: '#f8bbd0', d: '#d4a055', e: '#ffd54f' },
    sprite: [
      '..........',
      '..bbbbbb..',
      '.bbeccebb.',
      '.bbc..cbb.',
      '.bbc..cbb.',
      '.ddd..ddd.',
      '..dddddd..',
      '...dddd...',
      '..........',
      '..........',
    ],
  },
  {
    name: 'burger',
    palette: { a: '#5d4037', b: '#ff8f00', c: '#ffcc80', d: '#4caf50', e: '#795548' },
    sprite: [
      '..........',
      '...bbbb...',
      '..bccccb..',
      '..dddddd..',
      '..eeeeee..',
      '..eeeeee..',
      '..dddddd..',
      '..bccccb..',
      '...bbbb...',
      '..........',
    ],
  },
  {
    name: 'coffee',
    palette: { a: '#5d4037', b: '#ffffff', c: '#d7ccc8', d: '#795548', e: '#bcaaa4' },
    sprite: [
      '..d...d...',
      '...d.d....',
      '..bbbb....',
      '..bcccbdd.',
      '..bcccb.d.',
      '..bcccbdd.',
      '..bcccb...',
      '...bb.....',
      '.eeeeeee..',
      '..........',
    ],
  },
  {
    name: 'watermelon',
    palette: { a: '#2e7d32', b: '#e53935', c: '#ef9a9a', d: '#212121', e: '#1b5e20' },
    sprite: [
      '..........',
      '..........',
      '.aaaaaaaa.',
      '.abbbbbba.',
      '.abdcbdba.',
      '.abcbdbba.',
      '.abbbbbba.',
      '..eeeeee..',
      '..........',
      '..........',
    ],
  },
  {
    name: 'pizza',
    palette: { a: '#e65100', b: '#ffcc80', c: '#ffd54f', d: '#e53935', e: '#ff8f00' },
    sprite: [
      '..........',
      '.....a....',
      '....aba...',
      '....abba..',
      '...abcba..',
      '...abdba..',
      '..abcdba..',
      '..abccba..',
      '.aaaaaaaa.',
      '..........',
    ],
  },
  {
    name: 'cake',
    palette: { a: '#5d4037', b: '#f8bbd0', c: '#fce4ec', d: '#ffd54f', e: '#ff7043' },
    sprite: [
      '..........',
      '.....d....',
      '.....e....',
      '..bbbbbb..',
      '..bccccb..',
      '..bbbbbb..',
      '..bccccb..',
      '..bbbbbb..',
      '..........',
      '..........',
    ],
  },
  {
    name: 'balloon',
    palette: { a: '#9e9e9e', b: '#e53935', c: '#ef9a9a', d: '#c62828', e: '#757575' },
    sprite: [
      '..........',
      '...bbbb...',
      '..bccccb..',
      '..bcccbb..',
      '..bbbbbb..',
      '...bbbb...',
      '....eb....',
      '....a.....',
      '...a......',
      '..........',
    ],
  },
  {
    name: 'lollipop',
    palette: { a: '#795548', b: '#7b1fa2', c: '#ce93d8', d: '#e1bee7', e: '#4a148c' },
    sprite: [
      '..........',
      '...bbbb...',
      '..bcdcdb..',
      '..bdccdb..',
      '..bcdcdb..',
      '..bcccdb..',
      '...bbbb...',
      '....a.....',
      '....a.....',
      '....a.....',
    ],
  },
  {
    name: 'cherry',
    palette: { a: '#5d4037', b: '#c62828', c: '#e53935', d: '#ef9a9a', e: '#2e7d32' },
    sprite: [
      '..........',
      '....a.....',
      '...ea.a...',
      '..e.a..a..',
      '.bbb..bbb.',
      '.bcdbbcdb.',
      '.bccbbccb.',
      '..bb..bb..',
      '..........',
      '..........',
    ],
  },
  {
    name: 'fries',
    palette: { a: '#e65100', b: '#ffd54f', c: '#ffee58', d: '#c62828', e: '#ff8f00' },
    sprite: [
      '..........',
      '..b.bb.b..',
      '..b.bb.b..',
      '..bcbbcb..',
      '..bbbbbb..',
      '..adddda..',
      '..adddda..',
      '..adddda..',
      '...aaaa...',
      '..........',
    ],
  },
  {
    name: 'bubble-tea',
    palette: { a: '#5d4037', b: '#ffcc80', c: '#fff8e1', d: '#795548', e: '#4e342e' },
    sprite: [
      '..........',
      '....aa....',
      '..aabbaa..',
      '...bcccb..',
      '...bcccb..',
      '...bcccb..',
      '...bdddb..',
      '...bedeb..',
      '....bb....',
      '..........',
    ],
  },
  {
    name: 'cookie',
    palette: { a: '#8d6e63', b: '#d4a055', c: '#ffcc80', d: '#5d4037', e: '#4e342e' },
    sprite: [
      '..........',
      '...bbbb...',
      '..bdccdb..',
      '.bccccccb.',
      '.bcddcccb.',
      '.bcccddcb.',
      '.bccccccb.',
      '..bcccb...',
      '...bbbb...',
      '..........',
    ],
  },
];

function seededValue(seed, min, max) {
  let hash = 0;
  const text = String(seed);
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 33 + text.charCodeAt(index)) % 2147483647;
  }
  const ratio = (hash % 1000) / 1000;
  return min + ratio * (max - min);
}

function buildSprite(idea, width, height, spriteIndex) {
  const size = Math.round(seededValue(`${idea.id}-size`, 62, 78));
  const maxX = Math.max(14, width - size - 14);
  const maxY = Math.max(14, height - size - 14);

  let vx = seededValue(`${idea.id}-vx`, -0.36, 0.36);
  let vy = seededValue(`${idea.id}-vy`, -0.28, 0.28);
  if (Math.abs(vx) < 0.12) vx = vx >= 0 ? 0.16 : -0.16;
  if (Math.abs(vy) < 0.1) vy = vy >= 0 ? 0.14 : -0.14;

  const spriteDef = SPRITE_DEFS[spriteIndex % SPRITE_DEFS.length];
  return {
    id: idea.id,
    text: idea.text,
    size,
    x: seededValue(`${idea.id}-x`, 14, maxX),
    y: seededValue(`${idea.id}-y`, 14, maxY),
    vx,
    vy,
    driftPhaseX: seededValue(`${idea.id}-phase-x`, 0, Math.PI * 2),
    driftPhaseY: seededValue(`${idea.id}-phase-y`, 0, Math.PI * 2),
    driftSpeedX: seededValue(`${idea.id}-speed-x`, 0.0007, 0.0016),
    driftSpeedY: seededValue(`${idea.id}-speed-y`, 0.0009, 0.0018),
    driftAmountX: seededValue(`${idea.id}-drift-x`, 0.04, 0.12),
    driftAmountY: seededValue(`${idea.id}-drift-y`, 0.03, 0.09),
    spriteIndex,
    spriteName: spriteDef.name,
    sprite: spriteDef.sprite,
    palette: spriteDef.palette,
  };
}

function assignUniqueSprites(ideas, existingSprites, width, height) {
  const existingMap = new Map(existingSprites.map((sprite) => [sprite.id, sprite]));
  const used = new Set();

  return ideas.map((idea) => {
    const current = existingMap.get(idea.id);
    if (current && !used.has(current.spriteIndex)) {
      used.add(current.spriteIndex);
      return current;
    }

    let nextIndex = 0;
    while (used.has(nextIndex) && nextIndex < SPRITE_DEFS.length) {
      nextIndex += 1;
    }
    if (nextIndex >= SPRITE_DEFS.length) {
      nextIndex = used.size % SPRITE_DEFS.length;
    }
    used.add(nextIndex);
    return buildSprite(idea, width, height, nextIndex);
  });
}

function InspirationSprite({ sprite, palette, size, popping, onMouseEnter, onMouseLeave, onClick, label }) {
  const pixel = Math.max(4, Math.floor(size / SPRITE_SIZE));

  return (
    <button
      type="button"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
      aria-label={label}
      className={`relative transition-transform duration-150 hover:scale-105 ${popping ? 'animate-[idea-pop_320ms_steps(6,end)_forwards]' : ''}`}
      style={{
        width: `${pixel * SPRITE_SIZE}px`,
        height: `${pixel * SPRITE_SIZE}px`,
        imageRendering: 'pixelated',
        filter: 'drop-shadow(4px 4px 0 rgba(71,53,38,0.14))',
      }}
    >
      <div
        className="grid"
        style={{
          gridTemplateColumns: `repeat(${SPRITE_SIZE}, ${pixel}px)`,
          gridTemplateRows: `repeat(${SPRITE_SIZE}, ${pixel}px)`,
          width: `${pixel * SPRITE_SIZE}px`,
          height: `${pixel * SPRITE_SIZE}px`,
        }}
      >
        {sprite.flatMap((row, rowIndex) =>
          row.split('').map((cell, columnIndex) => {
            if (cell === '.') {
              return <span key={`${rowIndex}-${columnIndex}`} />;
            }
            return (
              <span
                key={`${rowIndex}-${columnIndex}`}
                style={{
                  width: `${pixel}px`,
                  height: `${pixel}px`,
                  background: palette[cell] || palette.a,
                }}
              />
            );
          })
        )}
      </div>
    </button>
  );
}

function InspirationBox({ ideas = [], onDismissIdea }) {
  const { t } = useLanguage();
  const boxRef = useRef(null);
  const frameRef = useRef(0);
  const spritesRef = useRef([]);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [renderSprites, setRenderSprites] = useState([]);
  const [hoveredId, setHoveredId] = useState(null);
  const [poppingIds, setPoppingIds] = useState([]);

  useEffect(() => {
    if (!boxRef.current) {
      return undefined;
    }
    const node = boxRef.current;
    const update = () => {
      const next = { width: node.clientWidth, height: node.clientHeight };
      setSize((current) =>
        current.width === next.width && current.height === next.height ? current : next
      );
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!size.width || !size.height) {
      return;
    }
    spritesRef.current = assignUniqueSprites(ideas, spritesRef.current, size.width, size.height);
    setRenderSprites([...spritesRef.current]);
  }, [ideas, size.height, size.width]);

  useEffect(() => {
    if (!size.width || !size.height || ideas.length === 0) {
      return undefined;
    }

    let last = performance.now();
    const animate = (now) => {
      const delta = Math.min(32, now - last || 16);
      last = now;
      const next = spritesRef.current.map((sprite) => {
        const maxX = Math.max(12, size.width - sprite.size - 12);
        const maxY = Math.max(12, size.height - sprite.size - 12);
        const driftX = Math.sin(now * sprite.driftSpeedX + sprite.driftPhaseX) * sprite.driftAmountX;
        const driftY = Math.cos(now * sprite.driftSpeedY + sprite.driftPhaseY) * sprite.driftAmountY;
        let x = sprite.x + (sprite.vx + driftX) * (delta / 16);
        let y = sprite.y + (sprite.vy + driftY) * (delta / 16);
        let vx = sprite.vx;
        let vy = sprite.vy;

        if (x <= 10 || x >= maxX) {
          vx *= -1;
          x = Math.max(10, Math.min(maxX, x));
        }
        if (y <= 10 || y >= maxY) {
          vy *= -1;
          y = Math.max(10, Math.min(maxY, y));
        }

        return { ...sprite, x, y, vx, vy };
      });

      spritesRef.current = next;
      setRenderSprites(next.map((sprite) => ({ ...sprite })));
      frameRef.current = window.requestAnimationFrame(animate);
    };

    frameRef.current = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(frameRef.current);
  }, [ideas.length, size.height, size.width]);

  const hoveredSprite = useMemo(
    () => renderSprites.find((sprite) => sprite.id === hoveredId) || null,
    [hoveredId, renderSprites]
  );

  const hoveredTooltip = useMemo(() => {
    if (!hoveredSprite) {
      return null;
    }

    const textLength = hoveredSprite.text.length;
    const width = Math.min(320, Math.max(132, textLength * 13 + 28));
    return {
      width,
      left: Math.min(
        Math.max(12, hoveredSprite.x + hoveredSprite.size + 10),
        Math.max(12, size.width - width - 12)
      ),
      top: Math.max(10, hoveredSprite.y),
    };
  }, [hoveredSprite, size.width]);

  const handlePop = (ideaId) => {
    if (poppingIds.includes(ideaId)) {
      return;
    }
    setPoppingIds((current) => [...current, ideaId]);
    window.setTimeout(() => {
      setPoppingIds((current) => current.filter((id) => id !== ideaId));
      if (onDismissIdea) {
        onDismissIdea(ideaId);
      }
    }, 320);
  };

  return (
    <section className="card py-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="font-mono text-xl uppercase tracking-[0.08em] text-[color:var(--text)]">
            {t.inspirationTitle}
          </h3>
          <p className="mt-1 text-sm text-[color:var(--muted)]">{t.inspirationSubtitle}</p>
        </div>
        <span
          className="font-mono text-xs uppercase tracking-[0.08em] text-[color:var(--text)]"
          style={{
            padding: '8px 12px',
            background: '#fff8eb',
            border: `3px solid ${PIXEL_BORDER}`,
            boxShadow: '4px 4px 0 rgba(98,76,52,0.18)',
          }}
        >
          {t.inspirationCount(ideas.length)}
        </span>
      </div>

      <div
        ref={boxRef}
        className="relative h-[228px] overflow-hidden"
        style={{
          backgroundColor: '#ffffff',
          backgroundImage:
            'linear-gradient(90deg, rgba(129,129,129,0.08) 1px, transparent 1px), linear-gradient(rgba(129,129,129,0.08) 1px, transparent 1px)',
          backgroundSize: '20px 20px, 20px 20px',
          backgroundPosition: '0 0, 0 0',
          border: `4px solid ${PIXEL_BORDER}`,
          boxShadow: '6px 6px 0 rgba(92,73,52,0.12), inset 0 0 0 3px rgba(255,255,255,0.9)',
        }}
      >
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-[12px]"
          style={{
            background: 'repeating-linear-gradient(90deg, rgba(90,90,90,0.08) 0 12px, transparent 12px 24px)',
          }}
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-55"
          style={{
            background:
              'radial-gradient(circle at 12% 16%, rgba(255,255,255,0.84) 0 1px, transparent 1px), radial-gradient(circle at 24% 72%, rgba(255,255,255,0.72) 0 1px, transparent 1px), radial-gradient(circle at 38% 28%, rgba(255,255,255,0.68) 0 1px, transparent 1px), radial-gradient(circle at 52% 52%, rgba(255,255,255,0.8) 0 1px, transparent 1px), radial-gradient(circle at 72% 18%, rgba(255,255,255,0.78) 0 1px, transparent 1px), radial-gradient(circle at 82% 44%, rgba(255,255,255,0.66) 0 1px, transparent 1px), linear-gradient(90deg, rgba(140,140,140,0.05) 1px, transparent 1px), linear-gradient(rgba(140,140,140,0.05) 1px, transparent 1px)',
            backgroundSize: '100% 100%, 100% 100%, 100% 100%, 100% 100%, 100% 100%, 100% 100%, 20px 20px, 20px 20px',
          }}
        />

        {ideas.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center px-6 text-center font-mono text-sm leading-6 text-[color:var(--muted)]">
            {t.inspirationEmpty}
          </div>
        ) : null}

        {renderSprites.map((sprite) => {
          const isPopping = poppingIds.includes(sprite.id);
          return (
            <div
              key={sprite.id}
              className="absolute"
              style={{ transform: `translate(${sprite.x}px, ${sprite.y}px)` }}
            >
              <InspirationSprite
                sprite={sprite.sprite}
                palette={sprite.palette}
                size={sprite.size}
                popping={isPopping}
                label={sprite.text}
                onMouseEnter={() => setHoveredId(sprite.id)}
                onMouseLeave={() => setHoveredId((current) => (current === sprite.id ? null : current))}
                onClick={() => handlePop(sprite.id)}
              />
            </div>
          );
        })}

        {hoveredSprite && hoveredTooltip ? (
          <div
            className="pointer-events-none absolute z-20 px-3 py-2 font-mono text-[11px] leading-5 text-white"
            style={{
              width: `${hoveredTooltip.width}px`,
              maxWidth: `min(${hoveredTooltip.width}px, calc(100% - 24px))`,
              left: hoveredTooltip.left,
              top: hoveredTooltip.top,
              background: '#302317',
              border: '3px solid #f7d29d',
              boxShadow: '4px 4px 0 rgba(53,40,26,0.28)',
              overflowWrap: 'anywhere',
              wordBreak: 'break-word',
              whiteSpace: 'normal',
            }}
          >
            {hoveredSprite.text}
          </div>
        ) : null}
      </div>

      <style>{`
        @keyframes idea-pop {
          0% { opacity: 1; transform: scale(1); }
          35% { opacity: 1; transform: scale(1.14); }
          68% { opacity: 0.96; transform: scale(0.84); }
          100% { opacity: 0; transform: scale(1.72); }
        }
      `}</style>
    </section>
  );
}

export default InspirationBox;
