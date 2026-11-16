// The green footer: ways to support the parks, then the how-it-works note
// and the not-affiliated disclaimer.

const SUPPORT_LINKS = [
  {
    href: 'https://www.nationalparks.org/donate',
    label: 'Donate to the National Park Foundation',
    note: 'The official charitable partner of the National Park Service',
  },
  {
    href: 'https://www.nps.gov/findapark/index.htm',
    label: 'Find a park near you',
    note: 'Search every National Park Service site by state or activity. Not near a National Park? Check out a National Monument, Historic Site, or other NPS site!',
  },
  {
    href: 'https://lnt.org/why/7-principles/',
    label: 'Leave No Trace principles',
    note: 'Seven simple ways to protect the places you visit',
  },
]

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="band-inner">
        <h2>Support the parks</h2>
        <ul className="support-links">
          {SUPPORT_LINKS.map((link) => (
            <li key={link.href}>
              <a href={link.href} target="_blank" rel="noreferrer">
                {link.label}
              </a>
              <span>{link.note}</span>
            </li>
          ))}
        </ul>

        <div className="disclaimer">
          <p>
            Puzzles and park stories are written with AI from National Park Service data and sourced research,
            checked against those sources, and reviewed by a person.{' '}
            <a href="https://github.com/mckennamc07/wild-guess" target="_blank" rel="noreferrer">
              See how it works
            </a>
            .
          </p>
          <p>Wild Guess is an independent project and is not affiliated with the U.S. National Park Service.</p>
        </div>
      </div>
    </footer>
  )
}
