import { Link } from 'react-router-dom'
import { ErrorState, Loading } from '../../components/State.jsx'
import { articlesInShelf, useArticles } from '../../content/ContentProvider.jsx'
import { useI18n } from '../../i18n/I18nContext.jsx'

const SHELF_STYLE = {
  A: { tone: 'blue', title: 'parents.shelfA', desc: 'parents.shelfADesc' },
  B: { tone: 'green', title: 'parents.shelfB', desc: 'parents.shelfBDesc' },
  C: { tone: 'amber', title: 'parents.shelfC', desc: 'parents.shelfCDesc' },
}

export function ArticleCard({ article, compact = false }) {
  const { t, tx } = useI18n()
  return (
    <Link to={`/parents/${article.id}`} className={`article-card tone-${article.color}`}>
      <span className="top">
        <span className="emoji" aria-hidden="true">
          {article.emoji}
        </span>
        <span className="meta">
          {article.id.toUpperCase()} · {article.minutes} {t('parents.minRead')}
        </span>
        {!compact && article.priority && <span className="priority-chip">{t('parents.priority')}</span>}
      </span>
      <h3>{tx(article.title)}</h3>
      {!compact && <span className="teaser">{tx(article.teaser)}</span>}
    </Link>
  )
}

function Shelf({ shelf, articles }) {
  const { t } = useI18n()
  const style = SHELF_STYLE[shelf]
  const list = articlesInShelf(articles, shelf)
  if (list.length === 0) return null
  return (
    <section className="shelf" aria-labelledby={`shelf-${shelf}`}>
      <div className="shelf-head">
        <h2 id={`shelf-${shelf}`}>
          <span className={`shelf-ic tone-${style.tone}`} aria-hidden="true">
            {shelf}
          </span>
          {t(style.title)}
        </h2>
        <p>{t(style.desc)}</p>
      </div>
      <div className="article-grid">
        {list.map((article) => (
          <ArticleCard key={article.id} article={article} />
        ))}
      </div>
    </section>
  )
}

export default function ParentsHubPage() {
  const { t } = useI18n()
  const articles = useArticles()
  return (
    <div className="fade-in">
      <Link to="/" className="back-btn">
        ← {t('nav.back')}
      </Link>
      <div className="hub-head">
        <span className="emoji" aria-hidden="true">
          🧭
        </span>
        <h1>{t('parents.title')}</h1>
        <p>{t('parents.intro')}</p>
      </div>

      {articles.status === 'loading' && <Loading />}
      {articles.status === 'error' && <ErrorState error={articles.error} onRetry={articles.reload} />}
      {articles.status === 'ready' && (
        <>
          <Shelf shelf="A" articles={articles.data.items} />

          <div className="hub-cta">
            <span className="emoji" aria-hidden="true">
              📝
            </span>
            <div className="body">
              <h2>{t('parents.agreementCta')}</h2>
              <p>{t('parents.agreementCtaText')}</p>
            </div>
            <Link to="/parents/agreement" className="btn-solid amber">
              {t('parents.openAgreement')}
            </Link>
          </div>

          <Shelf shelf="B" articles={articles.data.items} />
          <Shelf shelf="C" articles={articles.data.items} />

          <div className="hub-cta">
            <span className="emoji" aria-hidden="true">
              🆘
            </span>
            <div className="body">
              <h2>{t('emergency.title')}</h2>
              <p>{t('emergency.intro')}</p>
            </div>
            <Link to="/emergency" className="btn-solid">
              {t('emergency.open')}
            </Link>
          </div>
        </>
      )}
    </div>
  )
}
