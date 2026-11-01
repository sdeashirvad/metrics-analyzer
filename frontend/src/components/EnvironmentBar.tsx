export const ENVIRONMENT_NOTICE = 'Technology Risk is illustrative scenario data, not live Snowflake telemetry. Data Quality is read live from Snowflake.'

export function EnvironmentBar() {
  return (
    <div className="env-bar" role="note">
      <span className="env-dot" aria-hidden="true" />
      {ENVIRONMENT_NOTICE}
    </div>
  )
}
