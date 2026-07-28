import Link from 'next/link'

import { SiteFooter } from '@/components/landing/final-cta'
import { SiteHeader } from '@/components/landing/site-header'

export function LegalSection({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="border-t border-border pt-8">
      <h2 className="mb-4 font-mono text-base font-bold tracking-widest text-foreground uppercase md:text-lg">
        {title}
      </h2>
      <div className="flex flex-col gap-4 leading-relaxed text-pretty text-muted-foreground">
        {children}
      </div>
    </section>
  )
}

export function LegalList({ items }: { items: React.ReactNode[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {items.map((item, i) => (
        <li key={i} className="flex gap-3">
          <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

export function LegalPage({
  eyebrow,
  title,
  updated,
  children,
}: {
  eyebrow: string
  title: string
  updated: string
  children: React.ReactNode
}) {
  return (
    <>
      <SiteHeader />
      <main className="px-6 py-16 md:px-10 md:py-24">
        <article className="mx-auto flex max-w-3xl flex-col gap-10">
          <header className="flex flex-col gap-4">
            <p className="font-mono text-xs tracking-widest text-primary uppercase">
              {eyebrow}
            </p>
            <h1 className="font-mono text-3xl leading-tight font-bold text-balance text-foreground uppercase md:text-4xl">
              {title}
            </h1>
            <p className="font-mono text-xs tracking-wider text-muted-foreground uppercase">
              Обновлено: {updated}
            </p>
          </header>

          {children}

          <div className="border-t border-border pt-8">
            <Link
              href="/"
              className="font-mono text-xs tracking-widest text-primary uppercase hover:underline"
            >
              {'\u2190 На главную'}
            </Link>
          </div>
        </article>
      </main>
      <SiteFooter />
    </>
  )
}
