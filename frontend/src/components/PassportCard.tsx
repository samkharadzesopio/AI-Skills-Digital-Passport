import { fitCoverText, paginatePassport, PASSPORT_WIDTH, PASSPORT_HEIGHT, sectionTitles } from './passport-pagination'
import type { PassportPage } from './passport-pagination'
import { useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent } from 'react'
import './passport-card.css'

export type StampType = 'FOCUSED' | 'APPLIED' | 'ADVANCED'
export interface CardSkill {
  id: string; name: string; description: string | null; stampType: StampType | null
  experience: string | null; earnedOn: string | null
  learningExperiences?: { title: string | null; earnedOn: string | null }[]
}
export interface PassportCardData {
  demonstration: boolean; firstName: string; lastName: string; issuer: string | null
  reference: string | null; issuedOn: string | null; status: string; skills: CardSkill[]
}
const brand = (name: string) => `${import.meta.env.BASE_URL}brand/${name}`
export function OfficialBtuLogo({ className = '' }: { className?: string }) {
  return <img className={`official-btu-logo ${className}`} src={brand('btu-logo.svg')} alt="BTU — Business and Technology University" width="104" height="55"/>
}
const stamps = {
  FOCUSED: { title: 'AI Skill', format: 'Focused learning', file: 'ai_skill.png', description: 'An eligible workshop, masterclass, seminar, guest speaker session, or similar short-format learning experience.' },
  APPLIED: { title: 'AI Applied Skill', format: 'Applied learning', file: 'ai_applied.png', description: 'An extended practical learning experience, typically two to three days: an intensive workshop, bootcamp, hackathon, or challenge.' },
  ADVANCED: { title: 'AI Advanced Skill', format: 'Extended academic learning', file: 'ai_advanced.png', description: 'An eligible semester-long academic course with a defined and assessed AI competency in its learning outcomes.' },
} as const
function Stamp({ type }: { type: StampType | null }) {
  return type ? <img className="passport-learning-stamp" src={brand(stamps[type].file)} alt={`${stamps[type].title} — ${stamps[type].format}`} width="250" height="130"/> : <span className="passport-no-stamp">Stamp type not supplied</span>
}
function date(value: string | null) {
  if (!value) return 'Not supplied'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
}
function Lines({ values }: { values: string[] }) {
  return <>{values.map((line, index) => <span className="passport-text-line" key={index}>{line.replace(/\r?\n$/, '') || String.fromCharCode(160)}</span>)}</>
}
function FittedName({ value }: { value: string }) {
  const fit = fitCoverText(value || 'Not supplied', 340, 80)
  return <dd style={{ fontSize: fit.size, lineHeight: 1.15 }}><Lines values={fit.lines}/></dd>
}
function AboutPassport() {
  return <div className="passport-about-grid"><div className="passport-about-intro"><h2>ABOUT<br/>THE AI SKILLS<br/><span>DIGITAL PASSPORT</span></h2><p>Your personalized record of AI competencies developed throughout your university experience.</p><p>Stamps may be earned through eligible courses, workshops, masterclasses, hackathons, intensive programs, guest speaker sessions, and other AI learning experiences recognized by BTU.</p><p>Participation is voluntary. There is no required number or combination of stamps and no predefined pathway.</p><div className="passport-about-stars" aria-hidden="true">{[0, 1, 2, 3, 4].map(n => <img key={n} src={brand('passport-asterisk.svg')} alt=""/>)}</div></div><div className="passport-stamp-guide"><h2>UNDERSTANDING AI SKILLS STAMPS</h2><div className="passport-stamp-definitions">{(Object.keys(stamps) as StampType[]).map(type => <article key={type}><Stamp type={type}/><h3>{stamps[type].title}</h3><span>{stamps[type].format}</span><p>{stamps[type].description}</p></article>)}</div><aside><strong>IMPORTANT</strong><p>The three stamp types represent different learning formats and depths of engagement. They do not constitute a mandatory sequence.</p><p>You do not need an AI Skill before earning an AI Applied Skill or AI Advanced Skill.</p></aside></div></div>
}
function PageContent({ item, data, readable = false }: { item: PassportPage; data: PassportCardData; readable?: boolean }) {
  if (item.section === 0) return readable ? <dl><dt>Name</dt><dd>{data.firstName || 'Not supplied'}</dd><dt>Surname</dt><dd>{data.lastName || 'Not supplied'}</dd><dt>Issued on</dt><dd>{date(data.issuedOn)}</dd><dt>Issuer</dt><dd>{data.issuer || 'Not supplied'}</dd><dt>Passport reference</dt><dd>{data.demonstration ? 'Not issued' : data.reference || 'Not supplied'}</dd><dt>Status</dt><dd>{data.demonstration ? 'Demonstration only' : data.status}</dd></dl> : <>
    <div className="passport-cover-heading"><img src={brand('passport-title.svg')} alt="AI Skills Digital Passport" width="540" height="103"/><div className="passport-stars" aria-hidden="true">{[0, 1, 2].map(n => <img key={n} src={brand('passport-asterisk.svg')} alt=""/>)}</div></div>
    <div className="passport-cover-body"><dl className="passport-holder"><div><dt>NAME:</dt><FittedName value={data.firstName}/></div><div><dt>SURNAME:</dt><FittedName value={data.lastName}/></div><div><dt>DATE:</dt><dd>{date(data.issuedOn)}</dd></div></dl>
      <div className="passport-marks" aria-label="Passport artwork and record status"><div className="passport-issuer-mark">{data.demonstration ? 'DEMONSTRATION' : 'UNIVERSITY PASSPORT'}<small>{data.demonstration ? 'NOT AN ISSUED CREDENTIAL' : data.issuer || 'Issuer not supplied'}</small></div><img className="passport-green-seal" src={brand('passport-seal.svg')} alt="Original passport decorative AI seal; not verification evidence"/><div className="passport-cyan-mark" aria-hidden="true"><span>AI<br/>SKILLS<br/>DIGITAL PASSPORT</span></div><div className="passport-magenta-mark">{data.demonstration ? 'SAMPLE AI SKILLSET' : 'AI SKILLS RECORD'}</div></div>
    </div>
  </>
  if (item.section === 1) return <AboutPassport/>
  if (item.section === 2) return <div className="passport-skillset"><h2>VERIFIED AI SKILLSET</h2><p>{data.demonstration ? 'Illustrative stamps only. These skills have not been issued or verified.' : 'Recognized skills returned by your authorized university passport record.'}</p>{item.tiles.length ? <div className="passport-stamp-grid">{item.tiles.map((tile, index) => <article key={`${tile.skill.id}-${index}`} aria-label={tile.skill.name}><Stamp type={tile.skill.stampType}/>{tile.continued && <span className="passport-continuation">continued</span>}<h3><Lines values={tile.name.length ? tile.name : ['(continued)']}/></h3><p><Lines values={tile.experience}/></p></article>)}</div> : <div className="passport-skill-empty"><img src={brand('passport-asterisk.svg')} alt=""/><p>No recognized skills supplied for this passport.</p></div>}</div>
  const headings = ['Stamp type', 'Skill', 'Description', 'Earned through', 'Date earned']
  return <div className="passport-supplement"><h2>AI SKILL SUPPLEMENT</h2><p>{data.demonstration ? 'Fictional sample learning experiences — not verified records.' : 'Detailed record of skills and learning experiences supplied by the university.'}</p>{item.rows.length ? readable ? item.rows.map((row, index) => <article key={index}><h3>{row.skill.name}{row.continued ? ' (continued)' : ''}</h3><dl>{row.cells.map((cell, column) => cell.length ? <div key={column}><dt>{headings[column]}</dt><dd><Lines values={cell}/></dd></div> : null)}</dl></article>) : <table><colgroup>{[13, 18, 34, 21, 14].map((width, index) => <col key={index} style={{ width: `${width}%` }}/>)}</colgroup><thead><tr>{headings.map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{item.rows.map((row, index) => <tr key={index} style={{ height: row.height }} aria-label={`${row.skill.name}${row.continued ? ' (continued)' : ''}`}>{row.cells.map((cell, column) => <td key={column}><Lines values={cell}/>{column === 0 && row.continued && <span className="passport-row-continuation">continued</span>}</td>)}</tr>)}</tbody></table> : <p className="passport-skill-empty">No skill supplement records supplied.</p>}</div>
}
/** A fixed-aspect-ratio HTML canvas; variable records are paginated, never clipped. */
export function PassportCard({ data, compact = false }: { data: PassportCardData; compact?: boolean }) {
  const [page, setPage] = useState(0), [scale, setScale] = useState(1), id = useId()
  const viewport = useRef<HTMLDivElement>(null), touch = useRef<{ x: number; y: number } | null>(null)
  const pages = useMemo(() => paginatePassport(data.skills), [data.skills])
  const current = Math.min(page, pages.length - 1), selected = pages[current]
  useLayoutEffect(() => {
    const element = viewport.current
    if (!element) return
    const measure = () => { if (element.clientWidth > 0) setScale(element.clientWidth / PASSPORT_WIDTH) }
    measure()
    if (typeof ResizeObserver !== 'undefined') { const observer = new ResizeObserver(measure); observer.observe(element); return () => observer.disconnect() }
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])
  function go(next: number) { setPage(Math.max(0, Math.min(pages.length - 1, next))) }
  function key(event: KeyboardEvent<HTMLElement>) {
    if ((event.target as HTMLElement).closest('button, a, input, textarea, select, .passport-readable')) return
    if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) { event.preventDefault(); go(event.key === 'Home' ? 0 : event.key === 'End' ? pages.length - 1 : current + (event.key === 'ArrowRight' ? 1 : -1)) }
  }
  function pointerEnd(event: PointerEvent<HTMLElement>) {
    if (!touch.current) return
    const dx = event.clientX - touch.current.x, dy = event.clientY - touch.current.y
    touch.current = null
    if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.5) go(current + (dx < 0 ? 1 : -1))
  }
  const style = { '--passport-scale': scale, '--passport-height': `${PASSPORT_HEIGHT}px`, '--passport-ratio': `${PASSPORT_WIDTH} / ${PASSPORT_HEIGHT}` } as CSSProperties
  return <section className="passport-carousel" style={style} aria-label={data.demonstration ? 'Demonstration digital passport' : 'Your digital passport'} aria-roledescription="carousel" tabIndex={0} onKeyDown={key}>
    <div className="passport-context"><span>{data.demonstration ? 'DEMONSTRATION · FICTIONAL STUDENT · NOT ISSUED' : 'UNIVERSITY RECORD · INTERACTIVE WEB VIEW'}</span><span>04 SECTIONS / {pages.length} PAGES</span></div>
    <div className="passport-viewport" ref={viewport} onPointerDown={event => { if (event.pointerType === 'touch') { touch.current = { x: event.clientX, y: event.clientY }; event.currentTarget.setPointerCapture?.(event.pointerId) } }} onPointerUp={pointerEnd} onPointerCancel={() => { touch.current = null }}>
      <div className="passport-track" style={{ transform: `translateX(-${current * 100}%)` }}>
        {pages.map((item, index) => <section key={index} id={`${id}-view-${index}`} className={`passport-slide passport-slide-${item.section}`} aria-roledescription="slide" aria-label={`${index + 1} of ${pages.length}: ${item.title}${item.parts > 1 ? ` (${item.part}/${item.parts})` : ''}`} aria-hidden={current !== index} inert={current !== index}>
          <div className="passport-canvas">
            <div className="passport-institution-line"><span className="passport-ai-chip" aria-hidden="true">AI</span><span>A UNIVERSITY-WIDE INITIATIVE OF BUSINESS AND TECHNOLOGY UNIVERSITY (BTU)</span></div>
            <div className="passport-paper"><div className="passport-page-content">{Math.abs(index - current) <= 1 && <PageContent item={item} data={data}/>}</div><div className="passport-paper-footer"><span className="passport-small-title">AI SKILLS<br/><strong>DIGITAL PASSPORT</strong></span><OfficialBtuLogo/><span className="passport-reference">PASSPORT ID: <b>{data.demonstration ? 'NOT ISSUED' : data.reference || 'Not supplied'}</b></span></div></div>
            <div className="passport-frame-footer"><strong>BUSINESS AND TECHNOLOGY UNIVERSITY</strong><span>{data.demonstration ? 'DEMONSTRATION / UNVERIFIED' : data.status.replaceAll('_', ' ')}</span><span>{index + 1} / {pages.length}</span></div>
          </div>
        </section>)}
      </div>
    </div>
    <div className="passport-navigation"><button type="button" disabled={current === 0} onClick={() => go(current - 1)} aria-label="Previous passport view">←</button><div className="passport-view-tabs" role="group" aria-label="Passport sections">{sectionTitles.map((title, section) => <button type="button" key={title} aria-label={title} aria-pressed={selected.section === section} aria-controls={`${id}-view-${pages.findIndex(item => item.section === section)}`} onClick={() => go(pages.findIndex(item => item.section === section))}><span>{String(section + 1).padStart(2, '0')}</span><b>{title}</b></button>)}</div><button type="button" disabled={current === pages.length - 1} onClick={() => go(current + 1)} aria-label="Next passport view">→</button></div>
    <p className="passport-view-status" aria-live="polite" aria-atomic="true">{selected.title} · Page {current + 1} of {pages.length}{selected.parts > 1 ? ` · Section page ${selected.part} of ${selected.parts}` : ''}. {compact ? (data.demonstration ? 'Demonstration only / Not issued' : data.status.replaceAll('_', ' ')) : <>{data.demonstration ? 'Demonstration only. ' : ''}Blockchain proof not confirmed. Official issued PDFs remain available through the existing download controls.</>}</p>
    <details className="passport-readable"><summary>Read this page as text</summary><PageContent item={selected} data={data} readable/></details>
  </section>
}
