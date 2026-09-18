import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorState, Loading } from '../components/State.jsx'
import { useContent, useKnowledge } from '../content/ContentProvider.jsx'
import { useI18n } from '../i18n/I18nContext.jsx'
import { buildSystemPrompt, getKnowledgeSource, retrieve, selfHostedModel, setKnowledgeSource } from '../mascot/ioBrain.js'
import RobotCanvas from '../mascot/RobotCanvas.jsx'

/* IO Chat: the tutor answers ONLY from the Basic Cybersecurity Course text
   served by the platform API (GET /knowledge, feature-flagged).
   - "brain" mode: a self-hosted MLC model runs fully in the visitor's
     browser via WebLLM/WebGPU (CYBERHERO_TUTOR_MODEL_URL). Nothing the
     child types ever leaves the device - there is no server-side LLM and
     no third-party CDN.
   - "lookup" mode (no model configured / no WebGPU): IO shows the course
     passages that match the question. */

const STARTERS = [
  { en: 'What is phishing?', ka: 'რა არის ფიშინგი?' },
  { en: 'How do I make a strong password?', ka: 'როგორ შევქმნა ძლიერი პაროლი?' },
  { en: 'What is a VPN and when should I use it?', ka: 'რა არის VPN და როდის გამოვიყენო?' },
  { en: 'Disinformation vs misinformation?', ka: 'დეზინფორმაცია vs მისინფორმაცია?' },
]

export default function IoChatPage() {
  const { t, tx, lang } = useI18n()
  const { runtime } = useContent()
  const knowledge = useKnowledge(true)
  const [webgpu, setWebgpu] = useState(null) // null = checking
  const [loadState, setLoadState] = useState('idle') // idle | loading | ready | error
  const [progress, setProgress] = useState('')
  const [messages, setMessages] = useState([]) // {role:'user'|'assistant', content, sources?}
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const engineRef = useRef(null)
  const threadRef = useRef(null)
  const generationRef = useRef(0)
  const model = selfHostedModel(runtime.tutorModelUrl)
  const lookupOnly = !model || webgpu === false

  useEffect(() => {
    setWebgpu(Boolean(navigator.gpu))
  }, [])

  useEffect(() => {
    if (knowledge.status === 'ready' && getKnowledgeSource() !== knowledge.data) setKnowledgeSource(knowledge.data)
  }, [knowledge.status, knowledge.data])

  // auto-scroll the thread
  useEffect(() => {
    const el = threadRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, busy])

  useEffect(
    () => () => {
      engineRef.current?.unload?.()
    },
    [],
  )

  const loadModel = async () => {
    if (!model) return
    setLoadState('loading')
    setProgress('')
    try {
      const { CreateMLCEngine } = await import('@mlc-ai/web-llm')
      const eng = await CreateMLCEngine(model.model_id, {
        appConfig: model.appConfig,
        initProgressCallback: (p) => setProgress(p.text || ''),
      })
      engineRef.current = eng
      setLoadState('ready')
    } catch (err) {
      console.error(err)
      setProgress(String(err?.message || err))
      setLoadState('error')
    }
  }

  const canAsk = knowledge.status === 'ready' && (lookupOnly || loadState === 'ready')

  const send = async (rawText) => {
    const text = (rawText ?? input).trim()
    if (!text || busy || !canAsk) return
    setInput('')
    setBusy(true)
    const gen = ++generationRef.current
    const history = [...messages, { role: 'user', content: text }]

    if (lookupOnly) {
      const found = retrieve(text, 3)
      const content = found.length ? found.map((c) => c.en).join('\n\n') : t('mascot.chat.noMatch')
      setMessages([...history, { role: 'assistant', content, sources: found }])
      setBusy(false)
      return
    }

    const { prompt, sources } = buildSystemPrompt(text)
    setMessages([...history, { role: 'assistant', content: '', sources }])
    try {
      const stream = await engineRef.current.chat.completions.create({
        stream: true,
        messages: [
          { role: 'system', content: prompt },
          // short rolling window keeps small models focused
          ...history.slice(-8).map(({ role, content }) => ({ role, content })),
        ],
        temperature: 0.6,
        max_tokens: 320,
      })
      let acc = ''
      for await (const part of stream) {
        if (generationRef.current !== gen) return // thread was reset
        acc += part.choices?.[0]?.delta?.content || ''
        setMessages([...history, { role: 'assistant', content: acc, sources }])
      }
    } catch (err) {
      console.error(err)
      if (generationRef.current === gen) {
        setMessages([...history, { role: 'assistant', content: t('mascot.chat.genError'), sources: [] }])
      }
    } finally {
      if (generationRef.current === gen) setBusy(false)
    }
  }

  const reset = () => {
    generationRef.current += 1
    setMessages([])
    setBusy(false)
    engineRef.current?.resetChat?.()
  }

  const lastAssistant = messages[messages.length - 1]
  const ioTalking = busy && Boolean(lastAssistant?.content)
  const ioEmotion = busy && !lastAssistant?.content ? 'thinking' : 'happy'

  if (knowledge.status === 'loading') return <Loading />
  if (knowledge.status !== 'ready') return <ErrorState error={knowledge.error} onRetry={knowledge.reload} />

  return (
    <div className="fade-in io-chat">
      <Link to="/" className="back-btn">
        ← {t('nav.back')}
      </Link>

      <header className="hero mascot-hero">
        <span className="badge">🧪 {t('mascot.chat.badge')}</span>
        <h1>
          IO <span className="grad">Chat</span>
        </h1>
        <p>{t('mascot.chat.sub')}</p>
      </header>

      {model && webgpu === false && <div className="io-warn">⚠️ {t('mascot.chat.needsWebgpu')}</div>}

      <div className="io-chat-layout">
        <aside className="io-side">
          <RobotCanvas size={190} character="robot" label={t('mascot.widget.label')} emotion={ioEmotion} talking={ioTalking} follow idle />
          <div className="ctrl-group">
            <h2>{t('mascot.chat.model')}</h2>
            {!model && <p className="mascot-ctrl-note">{t('mascot.chat.noModel')}</p>}
            {model && loadState !== 'ready' && (
              <button type="button" className="btn-solid" disabled={loadState === 'loading' || webgpu === false} onClick={loadModel}>
                {loadState === 'loading' ? '⏳ ' + t('mascot.chat.loading') : '⬇️ ' + t('mascot.chat.load')}
              </button>
            )}
            {model && loadState === 'ready' && <p className="io-ready">✅ {t('mascot.chat.ready')}</p>}
            {loadState === 'loading' && <p className="io-progress">{progress}</p>}
            {loadState === 'error' && (
              <p className="io-warn">
                ⚠️ {t('mascot.chat.loadError')} {progress}
              </p>
            )}
            <p className="mascot-ctrl-note">{lookupOnly ? t('mascot.chat.lookupMode') : t('mascot.chat.privacy')}</p>
            <h2>{t('mascot.chat.topics')}</h2>
            <ul className="io-topics">
              {knowledge.data.sections.map((s) => (
                <li key={s.id}>{tx(s)}</li>
              ))}
            </ul>
          </div>
        </aside>

        <section className="io-thread-wrap" aria-label="IO chat">
          <div className="io-thread" ref={threadRef}>
            {messages.length === 0 && (
              <div className="io-msg io-msg-bot">
                <p>{t('mascot.chat.hello')}</p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`io-msg ${m.role === 'user' ? 'io-msg-user' : 'io-msg-bot'}`}>
                <p>{m.content || '…'}</p>
                {m.role === 'assistant' && m.sources?.length > 0 && m.content && (
                  <span className="io-sources">📚 {[...new Set(m.sources.map((s) => tx(s.title)))].slice(0, 3).join(' · ')}</span>
                )}
              </div>
            ))}
          </div>

          {messages.length === 0 && (
            <div className="chip-row io-starters">
              {STARTERS.map((s, i) => (
                <button key={i} type="button" className="chip-btn" disabled={!canAsk} onClick={() => send(tx(s))}>
                  {tx(s)}
                </button>
              ))}
            </div>
          )}

          <form
            className="io-input-row"
            onSubmit={(e) => {
              e.preventDefault()
              send()
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={canAsk ? t('mascot.chat.placeholder') : t('mascot.chat.placeholderIdle')}
              disabled={!canAsk || busy}
              aria-label={t('mascot.chat.placeholder')}
            />
            <button type="submit" className="btn-solid" disabled={!canAsk || busy || !input.trim()}>
              {t('mascot.chat.send')}
            </button>
            <button type="button" className="btn-ghost" onClick={reset} disabled={messages.length === 0}>
              {t('mascot.chat.reset')}
            </button>
          </form>
          <p className="io-disclaimer">{t('mascot.chat.disclaimer')}</p>
        </section>
      </div>

      <p className="mascot-fps u-center u-mt-14">
        IO Chat · {lang === 'ka' ? 'ქართული/English' : 'English/ქართული'} · {lookupOnly ? 'course lookup' : 'WebLLM (in-browser) + RAG'} · course-only
      </p>
    </div>
  )
}
