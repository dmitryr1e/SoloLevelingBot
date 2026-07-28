import { readFile } from 'node:fs/promises'
import { join } from 'node:path'

import { ImageResponse } from 'next/og'

// Next.js подхватывает этот файл автоматически по соглашению об именах:
// добавляет <meta property="og:image">/<meta name="twitter:image"> на каждой
// странице, где нет собственного opengraph-image, включая /privacy и /terms.
// Отдельный twitter-image.tsx не нужен — при его отсутствии Next.js для
// Twitter Card использует этот же файл.

export const alt = 'SoloLevelingBot — Система прокачает тебя'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

// Тот же файл, что и в bot/card.py (карточка охотника в самом боте) —
// один источник шрифта для всей визуальной айдентики проекта, поддерживает
// кириллицу (без этого русский заголовок отрисовался бы квадратами).
// `join(process.cwd(), ...)` — не url/import.meta: именно этот статически
// анализируемый паттерн трассировщик файлов Vercel (nft) распознаёт и кладёт
// ассет в бандл serverless-функции; произвольный относительный fetch() так
// не трассируется.
const RUSSO_ONE_PATH = join(process.cwd(), 'bot/assets/RussoOne-Regular.ttf')

// Цвета — ручной перевод токенов из app/globals.css (oklch → hex): satori
// (движок ImageResponse) не понимает oklch(), поэтому дублируем здесь.
// Приоритет — использованию @theme напрямую не подойдёт, названия совпадают
// сознательно, чтобы обновлять оба места синхронно при ребрендинге.
const COLORS = {
  background: '#181b24', // --background: oklch(0.16 0.015 250)
  card: '#1e222c', // --card: oklch(0.2 0.018 250)
  border: 'rgba(148, 219, 235, 0.18)', // --border: oklch(0.82 0.13 215 / 15%)
  primary: '#8fd9ea', // --primary: oklch(0.82 0.13 215)
  foreground: '#eef0f4', // --foreground: oklch(0.93 0.01 240)
  muted: '#9aa3b0', // --muted-foreground: oklch(0.65 0.015 240)
}

export default async function Image() {
  const russoOne = await readFile(RUSSO_ONE_PATH)

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          position: 'relative',
          background: COLORS.background,
          padding: '72px 88px',
        }}
      >
        {/* Свечение за заголовком — повторяет ambient-glow из hero.tsx */}
        <div
          style={{
            position: 'absolute',
            top: '-260px',
            left: '-160px',
            width: '760px',
            height: '760px',
            borderRadius: '50%',
            background:
              'radial-gradient(circle, rgba(143,217,234,0.22) 0%, rgba(143,217,234,0) 70%)',
            display: 'flex',
          }}
        />

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontFamily: 'Russo One',
            fontSize: 26,
            letterSpacing: 4,
            color: COLORS.primary,
            textTransform: 'uppercase',
          }}
        >
          <span>⟦ СИСТЕМА ⟧</span>
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            fontFamily: 'Russo One',
            fontSize: 76,
            lineHeight: 1.12,
            letterSpacing: 1,
            color: COLORS.foreground,
            textTransform: 'uppercase',
            marginTop: 28,
            maxWidth: 920,
          }}
        >
          <span>Ты получил</span>
          <span style={{ color: COLORS.primary }}>приглашение Системы</span>
        </div>

        <div
          style={{
            display: 'flex',
            fontFamily: 'Russo One',
            fontSize: 28,
            lineHeight: 1.5,
            color: COLORS.muted,
            marginTop: 32,
            maxWidth: 780,
          }}
        >
          Telegram-бот превращает твою жизнь в RPG: квесты, опыт, ранги от E до S
          и боссы недели
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '18px',
            marginTop: 56,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '14px 28px',
              borderRadius: 10,
              background: COLORS.primary,
              color: '#12141c',
              fontFamily: 'Russo One',
              fontSize: 26,
              letterSpacing: 1,
              textTransform: 'uppercase',
            }}
          >
            Принять контракт
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '14px 28px',
              borderRadius: 10,
              border: `1px solid ${COLORS.border}`,
              background: COLORS.card,
              color: COLORS.foreground,
              fontFamily: 'Russo One',
              fontSize: 24,
            }}
          >
            t.me/SystemAriseBot
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: 'Russo One', data: russoOne, style: 'normal', weight: 400 },
      ],
    }
  )
}
