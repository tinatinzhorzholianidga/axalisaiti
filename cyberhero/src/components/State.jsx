import { useI18n } from '../i18n/I18nContext.jsx'

/* Shared loading / error / empty states, styled like the rest of the app. */
export function Loading({ label }) {
  const { t } = useI18n()
  return (
    <div className="state-box" role="status" aria-live="polite">
      <span className="state-spinner" aria-hidden="true" />
      <p>{label || t('common.loading')}</p>
    </div>
  )
}

export function ErrorState({ error, onRetry, title }) {
  const { t } = useI18n()
  return (
    <div className="state-box state-error" role="alert">
      <span className="emoji" aria-hidden="true">
        🤖💤
      </span>
      <h2>{title || t('common.errorTitle')}</h2>
      <p>{error?.status === 404 ? t('common.notFoundText') : t('common.errorText')}</p>
      {onRetry && (
        <button type="button" className="btn-solid" onClick={onRetry}>
          ↻ {t('common.retry')}
        </button>
      )}
    </div>
  )
}

export function EmptyState({ emoji = '📭', children }) {
  return (
    <div className="state-box">
      <span className="emoji" aria-hidden="true">
        {emoji}
      </span>
      <p>{children}</p>
    </div>
  )
}
