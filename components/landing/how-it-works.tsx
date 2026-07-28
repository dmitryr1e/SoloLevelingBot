const STEPS = [
  {
    n: '01',
    title: 'Подпиши контракт',
    text: 'Открой бота, нажми /start — Система зарегистрирует тебя как охотника E-ранга и выдаст первые квесты.',
  },
  {
    n: '02',
    title: 'Выполняй квесты',
    text: 'Отмечай выполненное в один тап и присылай вечерний отчёт — ИИ оценит день и начислит опыт по характеристикам.',
  },
  {
    n: '03',
    title: 'Не пропускай дни',
    text: 'Каждый проваленный квест бьёт по HP. Ноль HP — смерть: минус уровень и обнуление опыта. Система не прощает.',
  },
  {
    n: '04',
    title: 'Поднимайся в рангах',
    text: 'Копи серии, бей боссов недели, открывай ачивки и достигай S-ранга. Твоя карточка охотника — твоё доказательство.',
  },
]

export function HowItWorks() {
  return (
    <section id="how" className="border-t border-border px-6 py-20 md:px-10">
      <div className="mx-auto max-w-6xl">
        <p className="mb-3 font-mono text-xs tracking-widest text-primary uppercase">
          {'// Протокол'}
        </p>
        <h2 className="mb-12 font-mono text-3xl font-bold text-balance text-foreground uppercase md:text-4xl">
          Как это работает
        </h2>
        <ol className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <li key={s.n} className="flex flex-col gap-3">
              <span className="font-mono text-4xl font-bold text-primary/40">{s.n}</span>
              <h3 className="font-bold text-foreground">{s.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{s.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
