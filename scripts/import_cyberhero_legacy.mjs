#!/usr/bin/env node
// One-off importer: converts the legacy CyberHero data modules
// (tinatinzhorzholianidga/Cyber-Learning-Platform, src/content/*) into the
// seed JSON files under seeds/cyberhero/. The seed files are the committed
// source of truth for `flask seed-cyberhero`; rerun this only to re-import.
//
//   node scripts/import_cyberhero_legacy.mjs /path/to/Cyber-Learning-Platform
import { mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const legacy = resolve(process.argv[2] || '../cyber-learning-platform')
const out = resolve('seeds/cyberhero')
mkdirSync(out, { recursive: true })

const TONES = {
  '#5b8cff': 'blue',
  '#00b5d8': 'cyan',
  '#3ecf8e': 'green',
  '#e05780': 'pink',
  '#ffb020': 'amber',
  '#8b5cff': 'violet',
  '#ff8c42': 'orange',
  '#6c5ce7': 'accent',
}
const tone = (hex) => {
  const t = TONES[String(hex).toLowerCase()]
  if (!t) throw new Error(`unknown colour ${hex}`)
  return t
}

const load = async (rel) => (await import(pathToFileURL(join(legacy, 'src', rel)).href))
const write = (name, data) => {
  const path = join(out, name)
  writeFileSync(path, JSON.stringify(data, null, 2) + '\n')
  console.log(`wrote ${path}`)
}

// ---- tiers → tracks ---------------------------------------------------------
const { TIERS, PARENTS_TIER } = await load('content/tiers.js')
const tiers = [...TIERS, PARENTS_TIER].map((t, i) => ({
  ...t,
  color: tone(t.color),
  sort_order: i + 1,
  audience: t.id === 'parents' ? 'parents' : ['kids', 'cadets'].includes(t.id) ? 'kids' : t.id === 'guardians' ? 'teens' : 'adults',
}))
write('tiers.json', { tiers, parentsId: PARENTS_TIER.id })

// ---- missions ---------------------------------------------------------------
const { MISSIONS } = await load('content/guardians/index.js')
const mascot = await load('content/mascot.js')
// MISSION_TOPICS is module-private in the legacy file; mirror it here.
const MISSION_TOPICS = {
  g1: ['phishing'], g2: ['privacy'], g3: ['passwords'], g4: ['help', 'strangers'], g5: ['scams'],
  g6: ['kindness', 'help'], g7: ['fake'], g8: ['strangers', 'help'], g9: ['balance'], g10: [],
}
const missions = MISSIONS.map((m) => ({
  ...m,
  color: tone(m.color),
  track: 'guardians',
  topics: MISSION_TOPICS[m.id] || [],
}))
write('missions.json', missions)

// ---- articles ---------------------------------------------------------------
const { ARTICLES } = await load('content/parents/index.js')
const articles = ARTICLES.map((a) => ({ ...a, color: tone(a.color) }))
write('articles.json', articles)

// ---- agreement --------------------------------------------------------------
const agreement = (await load('content/parents/agreement.js')).default
write('agreement.json', agreement)

// ---- mascot -----------------------------------------------------------------
write('mascot.json', {
  tips: mascot.MASCOT_TIPS,
  reactions: mascot.MASCOT_REACTIONS,
  checklist: mascot.MASCOT_CHECKLIST,
})

// ---- IO knowledge base (Basic Cybersecurity Course, elearning.gov.ge id=18) --
const { IO_COURSE } = await load('content/ioCourse.js')
write('knowledge.json', IO_COURSE)

// ---- CyberHero course: the Guardians theory track ---------------------------
// Each core mission's "theory in 60 seconds" becomes a short reading lesson
// that links to the mission; modules group them by theme.
const groups = [
  { slug: 'messages-and-traps', title: { en: 'Messages and traps', ka: 'შეტყობინებები და ხაფანგები' }, missions: ['g1', 'g5', 'g7'] },
  { slug: 'you-online', title: { en: 'You, online', ka: 'შენ - ინტერნეტში' }, missions: ['g2', 'g3', 'g9'] },
  { slug: 'people-and-pressure', title: { en: 'People and pressure', ka: 'ადამიანები და ზეწოლა' }, missions: ['g4', 'g6', 'g8'] },
]
const byId = Object.fromEntries(missions.map((m) => [m.id, m]))
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const lessonHtml = (m, lang) => {
  const bullets = m.theory.map((p) => `<li>${esc(p[lang])}</li>`).join('\n')
  const practice = lang === 'ka' ? 'ივარჯიშე მისიაში' : 'Practise it in the mission'
  return `<p>${esc(m.brief[lang])}</p>\n<h3>${lang === 'ka' ? 'თეორია 60 წამში' : 'The theory in 60 seconds'}</h3>\n<ul>\n${bullets}\n</ul>\n<blockquote>${esc(m.takeaways[0][lang])}</blockquote>\n<p><a href="/cyberhero/guardians/mission/${m.id}">${practice}: ${esc(m.name[lang])} →</a></p>`
}
const course = {
  slug: 'cyber-guardians',
  track: 'guardians',
  emoji: '🛡️',
  color: 'blue',
  difficulty: 'beginner',
  estimated_minutes: 60,
  age_min: 13,
  age_max: 18,
  tags: ['phishing', 'passwords', 'privacy', 'scams', 'wellbeing'],
  is_featured: true,
  title: { en: 'Cyber Guardians: the theory track', ka: 'კიბერ დამცველები: თეორიის ტრეკი' },
  short_description: {
    en: 'Nine short reads that prepare you for the ten Guardian missions - phishing, passwords, scams, privacy, blackmail, bullying, fakes and balance.',
    ka: 'ცხრა მოკლე საკითხავი, რომელიც ათი დამცველის მისიისთვის გამზადებს - ფიშინგი, პაროლები, თაღლითობა, პრივატულობა, შანტაჟი, ბულინგი, ყალბი ამბები და ბალანსი.',
  },
  description: {
    en: '<p>Every Guardian mission starts with "the theory in 60 seconds". This track collects those pages so you can read them first, at your own pace, then jump into the mission to practise.</p><p>Finish the reads, then complete all ten missions to earn the Guardian Certificate.</p>',
    ka: '<p>დამცველის ყველა მისია „თეორია 60 წამში“ იწყება. ეს ტრეკი ამ გვერდებს ერთად აგროვებს, რომ ჯერ შენს ტემპში წაიკითხო და მერე მისიაში ივარჯიშო.</p><p>წაიკითხე ყველა გაკვეთილი, შემდეგ დაასრულე ათივე მისია და მოიპოვე დამცველის სერტიფიკატი.</p>',
  },
  objectives: {
    en: ['Spot phishing, scams and fake content before they cost you', 'Build passwords and accounts attackers give up on', 'Know exactly what to do when someone threatens or pressures you online', 'Keep screens, sleep and friendships in balance'],
    ka: ['ამოიცანი ფიშინგი, თაღლითობა და ყალბი კონტენტი, სანამ ზიანს მოგაყენებს', 'ააგე პაროლები და ანგარიშები, რომლებზეც თავდამსხმელი ხელს ჩაიქნევს', 'ზუსტად იცოდე, რა გააკეთო, როცა ვინმე ონლაინ გემუქრება ან ზეწოლას ახდენს', 'შეინარჩუნე ბალანსი ეკრანებს, ძილსა და მეგობრობას შორის'],
  },
  audience: { en: 'Grades 8-12 · ages 13-18', ka: '8-12 კლასი · 13-18 წელი' },
  modules: groups.map((g) => ({
    slug: g.slug,
    title: g.title,
    description: { en: '', ka: '' },
    lessons: g.missions.map((id) => {
      const m = byId[id]
      return {
        slug: `${m.id}-${m.name.en.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`,
        type: 'reading',
        minutes: 5,
        mission: m.id,
        title: m.name,
        summary: m.desc,
        content: { en: lessonHtml(m, 'en'), ka: lessonHtml(m, 'ka') },
      }
    }),
  })),
}
write('courses.json', [course])
console.log(`missions ${missions.length}, articles ${articles.length}, tiers ${tiers.length}, knowledge sections ${IO_COURSE.sections.length}`)
