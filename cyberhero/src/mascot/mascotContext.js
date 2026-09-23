/* IO's tips and reactions come from the API (`mascot` in the bootstrap
   payload, editable in the admin panel). Tips are tagged with topics so
   the mascot can match what he says to where the user is. */

const EMPTY = { tips: [], reactions: {}, missionTopics: {} }

// The Teachers & Parents track is a course now (`/course/teachers-parents`);
// the legacy hub paths still redirect there.
export function isParentsPath(pathname) {
  return (
    pathname.startsWith('/parents') ||
    pathname.startsWith('/articles') ||
    pathname.startsWith('/family-agreement') ||
    pathname.startsWith('/course/teachers-parents') ||
    pathname.startsWith('/learn/teachers-parents')
  )
}

export function splitTips(mascot = EMPTY) {
  const tips = mascot.tips || []
  return {
    kid: tips.filter((tip) => !(tip.topics || []).includes('parents')),
    parent: tips.filter((tip) => (tip.topics || []).includes('parents')),
  }
}

/* Resolve what the helper should say for a route (app-relative pathname).
   Returns { tips, opener? } - opener is an optional context greeting. */
export function getMascotContext(pathname = '/', mascot = EMPTY) {
  const { kid, parent } = splitTips(mascot)
  const reactions = mascot.reactions || {}
  if (pathname.startsWith('/track/')) {
    return { tips: kid, opener: reactions.building }
  }
  const mission = pathname.match(/^\/guardians\/mission\/([^/]+)/)
  if (mission) {
    const topics = (mascot.missionTopics || {})[mission[1]] ?? []
    const pool = kid.filter((tip) => (tip.topics || []).some((topic) => topics.includes(topic)))
    return { tips: pool.length ? pool : kid }
  }
  if (pathname.startsWith('/guardians/certificate')) {
    return { tips: kid, opener: reactions.cert }
  }
  if (pathname.startsWith('/guardians')) {
    return { tips: kid, opener: reactions.guardians }
  }
  if (isParentsPath(pathname)) {
    return { tips: [...parent, ...kid.filter((tip) => (tip.topics || []).includes('help'))] }
  }
  if (pathname.startsWith('/emergency')) {
    return { tips: kid.filter((tip) => (tip.topics || []).includes('help')) }
  }
  return { tips: kid }
}

export function missionReaction(mascot, index) {
  const list = mascot?.reactions?.mission || []
  if (!list.length) return null
  return list[index % list.length]
}

/* What IO says when the visitor hovers (or focuses) a track card on the
   welcome page: the admin-edited "track.<id>" reactions in turn, falling
   back to the track's own intro / description so every card gets a line.
   `index` counts the visits so repeated hovers walk through the pool. */
export function trackHint(mascot, tier, index = 0) {
  if (!tier) return null
  const pool = ((mascot?.reactions?.tracks || {})[tier.id] || []).filter((line) => line && (line.en || line.ka))
  if (pool.length) return pool[((index % pool.length) + pool.length) % pool.length]
  const own = [tier.intro, tier.desc].find((text) => text && (text.en || text.ka))
  return own || null
}
