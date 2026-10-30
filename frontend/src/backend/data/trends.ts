export interface RawTrendPoint {
  date: string
  value: number
  unconfirmedAmber?: boolean
}

export const trends: Record<string, RawTrendPoint[]> = {
  M001: [
    { date: '2026-10-08', value: 98.6 },
    { date: '2026-10-09', value: 98.4 },
    { date: '2026-10-10', value: 98.1 },
    { date: '2026-10-11', value: 97.2 },
    { date: '2026-10-12', value: 96.4 },
    { date: '2026-10-13', value: 95.6 },
    { date: '2026-10-14', value: 93.8 },
    { date: '2026-10-16', value: 92.9 },
    { date: '2026-10-18', value: 92.1 },
    { date: '2026-10-20', value: 91.4 },
    { date: '2026-10-22', value: 91 },
    { date: '2026-10-24', value: 90.6 },
    { date: '2026-10-27', value: 90.4 },
  ],
  M003: [
    { date: '2026-10-08', value: 8 },
    { date: '2026-10-10', value: 9 },
    { date: '2026-10-12', value: 12 },
    { date: '2026-10-14', value: 18 },
    { date: '2026-10-16', value: 27 },
    { date: '2026-10-18', value: 31 },
    { date: '2026-10-20', value: 34 },
    { date: '2026-10-22', value: 37 },
    { date: '2026-10-24', value: 39 },
    { date: '2026-10-27', value: 41 },
  ],
  M004: [
    { date: '2026-10-16', value: 99.6 },
    { date: '2026-10-18', value: 99.2, unconfirmedAmber: true },
    { date: '2026-10-20', value: 98.6, unconfirmedAmber: true },
    { date: '2026-10-21', value: 98.2, unconfirmedAmber: true },
    { date: '2026-10-22', value: 97.6 },
    { date: '2026-10-24', value: 97.2 },
    { date: '2026-10-27', value: 97 },
  ],
  M007: [
    { date: '2026-09-27', value: 4.2 },
    { date: '2026-10-04', value: 6.1 },
    { date: '2026-10-11', value: 8.7 },
    { date: '2026-10-18', value: 12.6 },
    { date: '2026-10-25', value: 14.1 },
  ],
}
