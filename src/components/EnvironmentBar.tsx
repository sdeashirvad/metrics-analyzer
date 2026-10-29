export const ENVIRONMENT_NOTICE = 'Demo environment · No live SMARTS, Snowflake, or Cortex connection'

export function EnvironmentBar() {
  return (
    <div className="env-bar" role="note">
      <span className="env-dot" aria-hidden="true" />
      {ENVIRONMENT_NOTICE}
    </div>
  )
}
