// Shared helpers used by ArticleCard and ArticleDetailPage.

export function getDomain(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return url
  }
}

export function scoreBadgeClass(score) {
  if (score == null) return 'badge badge--grey'
  if (score >= 8)   return 'badge badge--green'
  if (score >= 5)   return 'badge badge--amber'
  return                   'badge badge--grey'
}
