const FEATURES = [
  {
    code: 'QUEST.DAILY',
    title: 'Ежедневные квесты',
    text: 'Каждое утро Система выдаёт квесты: спорт, учёба, дисциплина. Выполнил — опыт. Провалил — потеря HP. HP на нуле — смерть и минус уровень.',
  },
  {
    code: 'AI.JUDGE',
    title: 'ИИ-оценка отчётов',
    text: 'Опиши, что сделал за день, — ИИ Системы оценит конкретику и усилия, начислит опыт и распределит его по характеристикам. Обмануть не выйдет.',
  },
  {
    code: 'STREAK.CHAIN',
    title: 'Серии и заморозки',
    text: 'Дни без провалов складываются в серию. Вехи на 3, 7, 14, 30, 60 и 100 дней дают бонусный опыт и заморозки, спасающие серию от срыва.',
  },
  {
    code: 'BOSS.WEEKLY',
    title: 'Босс недели',
    text: 'Весь сервер вместе бьёт одного босса: каждый заработанный XP — урон. Добили — награда всем участникам рейда.',
  },
  {
    code: 'GATE.RANDOM',
    title: 'Врата',
    text: 'Иногда перед тобой открываются врата — бонус-квест повышенной сложности с повышенной наградой. Закрываются в полночь.',
  },
  {
    code: 'RANK.LADDER',
    title: 'Ранги E → S',
    text: 'Прокачивай силу, интеллект, выносливость, ловкость и харизму. Поднимайся от E-ранга до S и сравнивай себя с другими охотниками в рейтинге.',
  },
]

export function Features() {
  return (
    <section className="border-t border-border px-6 py-20 md:px-10">
      <div className="mx-auto max-w-6xl">
        <p className="mb-3 font-mono text-xs tracking-widest text-primary uppercase">
          {'// Возможности Системы'}
        </p>
        <h2 className="mb-12 font-mono text-3xl font-bold text-balance text-foreground uppercase md:text-4xl">
          Механики, которые не дадут тебе слиться
        </h2>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <article
              key={f.code}
              className="rounded-lg border border-border bg-card p-6 transition-colors hover:border-primary/40"
            >
              <p className="mb-3 font-mono text-xs tracking-widest text-primary uppercase">
                {f.code}
              </p>
              <h3 className="mb-2 text-lg font-bold text-foreground">{f.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{f.text}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
