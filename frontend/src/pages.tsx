import { useQuery } from '@tanstack/react-query'
import { ArrowDownToLine, Award, Check } from 'lucide-react'
import { getDemoStudent } from './data/mock'
import { demoPassport } from './data/passport'
import { PassportCard } from './components/PassportCard'
import { structuredPassportCard } from './components/passport-card-data'
import { PassportPreview } from './components/PassportPreview'
import { Card, EmptyState } from './components/ui'
function Passport({ showTemplate = false }: { showTemplate?: boolean }) { return <PassportPreview passport={demoPassport} showTemplate={showTemplate}/> }
function Skills() { return <div className="skill-list">{useStudent().data?.skills.map(s => <div key={s.name}><div className="skill-label"><span><i style={{ background: s.color }}/>{s.name}</span><b>{s.progress}<small>%</small></b></div><div className="progress"><div style={{ width: `${s.progress}%`, background: s.color }}/></div></div>)}</div> }
function useStudent() { return useQuery({ queryKey: ['demo-student'], queryFn: getDemoStudent }) }
function Credentials() { const { data } = useStudent(); return <div className="credential-list">{data?.credentials.length ? data.credentials.map(c => <div className="credential" key={c.id}><div className="credential-icon"><Award size={23}/></div><div><h3>{c.title}</h3><p>{c.issuer} <span>·</span> {c.date}</p></div><span className="badge"><Check size={12}/>Demo credential</span></div>) : <EmptyState title="No credentials yet">Your issued credentials will appear here.</EmptyState>}</div> }
export function Dashboard() { return <section className="dashboard-passport" aria-label="Your Digital Passport"><PassportCard data={structuredPassportCard(demoPassport)} compact/><div className="dashboard-passport-actions"><button className="button" disabled>Download PDF</button><button className="button" disabled>Share Passport</button><button className="button" disabled>View History</button></div><p className="muted">Demo Mode: no issued PDF, public reference, or passport history is available.</p></section> }
export function Detail({ page }: { page: string }) { return <><h1>{page}</h1><p className="muted">Explore your learning journey · Demonstration data</p><Card>{page === 'AI skills & competencies' ? <Skills/> : page === 'Verified credentials' ? <><p className="notice">Sample credentials only. These are not university-issued records.</p><Credentials/></> : <><Passport showTemplate/><p className="notice">Preview only. Export and sharing will be enabled when university issuance is connected.</p><button className="button" disabled><ArrowDownToLine size={16}/> Export PDF · Coming soon</button></>}</Card></> }
export function Gap() { return <Card><h1>Skills Gap Analyzer</h1><EmptyState title="Coming Soon">University-approved competency mappings are not available yet.</EmptyState></Card> }
