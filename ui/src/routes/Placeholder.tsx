function Placeholder({ title, arrival }: { title: string; arrival: string }) {
  return (
    <section className="px-10 py-10 lg:px-14">
      <h1 className="font-display text-xl">{title}</h1>
      <p className="mt-2 text-text-dim">{arrival}</p>
    </section>
  )
}

export function Playground() {
  return <Placeholder title="Playground" arrival="Arrives in PR C." />
}

export function Bench() {
  return <Placeholder title="Bench" arrival="Arrives in PR D." />
}
