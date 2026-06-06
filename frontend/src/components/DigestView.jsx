/**
 * DigestView.jsx
 *
 * Renders this week's digest if one has been generated, otherwise nothing.
 * The digest content is markdown stored as plain text — we render it as
 * preformatted text for now. A markdown renderer can be added later.
 */

/**
 * @param {object|null} digest - digest object from GET /digest/current, or null
 */
export default function DigestView({ digest }) {
  if (!digest) return null

  return (
    <section className="digest">
      <h2 className="digest__heading">Week {digest.week_number} Digest</h2>
      <pre className="digest__content">{digest.content}</pre>
    </section>
  )
}
