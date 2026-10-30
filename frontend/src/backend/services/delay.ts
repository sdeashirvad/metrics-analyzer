export const MOCK_DELAY_MS = 180

export function delay(ms = MOCK_DELAY_MS): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}
