// "Today" for Wild Guess is the date in U.S. Eastern time, wherever the
// player is. Intl handles daylight saving time, so there's no hard-coded
// UTC offset (that was v1's bug: puzzles went live at 11 pm in winter).
//
// Why it matters: everyone gets the same puzzle on the same day, and it
// changes at midnight Eastern all year round.

export function easternToday(now: Date = new Date()): string {
  // 'en-CA' formats dates as YYYY-MM-DD, the same format as puzzle_date.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)
}

export function formatPuzzleDate(isoDate: string): string {
  // Noon UTC so the weekday can't shift across a time zone boundary.
  return new Date(`${isoDate}T12:00:00Z`).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}
