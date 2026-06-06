import AgentTrace from './AgentTrace'

export default function DigestView({ digest }) {
  if (!digest) return null

  return (
    <section className="digest">
      <h2 className="digest__heading">Week {digest.week_number} Digest</h2>
      <pre className="digest__content">{digest.content}</pre>
      <AgentTrace trace={digest.trace} />
    </section>
  )
}
