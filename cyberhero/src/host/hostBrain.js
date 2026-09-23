/* IO's home-page brain: decides WHICH line he says and HOW he feels.

   On the eLearning home page IO is a host, not a teacher - his lines
   welcome people and route them to the right course (see hints.js) through
   the page's two "doors", the Browse courses and Open CyberHero buttons.
   This module never touches the 3D model; it only picks lines, emotions
   and gestures for the IoHost component to play. */

import { HINTS } from './hints.js'

/* how IO feels while saying each kind of line */
export const MOOD = {
  greeting: 'happy',
  morning: 'happy',
  afternoon: 'happy',
  evening: 'sleepy',
  whoAmI: 'wink',
  pickPath: 'thinking',
  basicCourse: 'happy',
  kidsPlatform: 'excited',
  login: 'happy',
  certificate: 'celebrate',
  language: 'wink',
  aboutDga: 'happy',
  encouragement: 'celebrate',
  hoverBasic: 'thinking',
  hoverKids: 'excited',
  farewell: 'celebrate',
}

/* the order IO walks through when the visitor keeps clicking him -
   orientation first, then the two paths, then the small print, and a
   cheer sprinkled in between */
export const CYCLE = [
  'pickPath',
  'basicCourse',
  'kidsPlatform',
  'encouragement',
  'login',
  'whoAmI',
  'certificate',
  'aboutDga',
  'language',
  'encouragement',
]

/* a line that only makes sense while the CyberHero door is on the page:
   it names CyberHero or talks about "both / two paths" */
const MENTIONS_KIDS = /CyberHero|კიბერგმირ|both paths|two paths|ორივე გზა|ორი გზა/i
export function mentionsKids(line) {
  return MENTIONS_KIDS.test(`${line.en} ${line.ka}`)
}

export function timeOfDay(date = new Date()) {
  const h = date.getHours()
  if (h < 12) return 'morning'
  if (h < 18) return 'afternoon'
  return 'evening'
}

/* A tiny stateful host: round-robin inside each category, round-robin
   across the CYCLE, so nothing repeats until the pool is exhausted.
   `seed` just rotates the starting point so two page loads don't always
   open with the same second line. `doors` lists the doors on the page
   ('basic', 'kids'); without the kids door every line that points to
   CyberHero is dropped (and a category left empty is skipped). A signed-in
   visitor is not told where the sign-in button is. */
export function createHost({ seed = 0, date = new Date(), doors = ['basic', 'kids'], signedIn = false } = {}) {
  const kids = doors.includes('kids')
  const pools = {}
  for (const [key, lines] of Object.entries(HINTS)) {
    if (!Array.isArray(lines)) continue
    pools[key] = kids ? lines : lines.filter((line) => !mentionsKids(line))
  }
  if (signedIn) pools.login = []
  const cursor = {}
  const pick = (key) => {
    const pool = pools[key] || []
    if (!pool.length) return null
    const i = (cursor[key] ?? (seed % pool.length)) % pool.length
    cursor[key] = i + 1
    return { key, line: pool[i], mood: MOOD[key] || 'happy' }
  }
  const cycle = CYCLE.filter((key) => pools[key]?.length)
  let step = 0 // the cycle always starts with orientation; seed only rotates lines inside a pool

  return {
    /* first thing he says: a time-of-day greeting */
    greet() {
      return pick(timeOfDay(date)) || pick('greeting')
    },
    /* second beat after the greeting: introduce himself */
    intro() {
      return pick('whoAmI')
    },
    /* every click on IO walks the cycle */
    next() {
      const key = cycle[step % cycle.length]
      step += 1
      return pick(key)
    },
    /* the visitor is hovering / focusing one of the doors */
    hover(card) {
      return pick(card === 'kids' ? 'hoverKids' : 'hoverBasic')
    },
    /* the visitor chose a path */
    farewell() {
      return pick('farewell')
    },
  }
}
