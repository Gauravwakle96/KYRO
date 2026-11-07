import type { ReactNode } from 'react'
import { AlertCircle, ArrowRight, Check, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

export function Badge({ value }: { value: string }) { return <span className={'badge tone-' + value.toLowerCase().replaceAll('_', '-')}><span />{value.replaceAll('_', ' ')}</span> }
export function PageTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) { return <header className="page-heading"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</header> }
export function Loading({ label = 'Loading workspace' }: { label?: string }) { return <div className="state loading" role="status"><LoaderCircle className="spin" size={20} /><span>{label}…</span></div> }
export function ErrorState({ error, retry }: { error: Error; retry?: () => void }) { return <div className="state error" role="alert"><AlertCircle size={20} /><div><strong>{error.message}</strong>{retry && <button className="text-button" onClick={retry}>Try again <ArrowRight size={14} /></button>}</div></div> }
export function Empty({ title, detail, href, action }: { title: string; detail: string; href?: string; action?: string }) { return <div className="state empty"><div className="empty-symbol">↗</div><h2>{title}</h2><p>{detail}</p>{href && <Link className="button secondary" to={href}>{action ?? 'Get started'}<ArrowRight size={15} /></Link>}</div> }
export function Success({ children }: { children: ReactNode }) { return <div className="notice success" role="status"><Check size={16} />{children}</div> }
export function Notice({ children }: { children: ReactNode }) { return <div className="notice"><AlertCircle size={16} />{children}</div> }
export function Panel({ title, children, extra }: { title: string; children: ReactNode; extra?: ReactNode }) { return <section className="panel"><div className="panel-heading"><h2>{title}</h2>{extra}</div>{children}</section> }
export function Code({ children }: { children: string }) { return <pre className="code" tabIndex={0}><code>{children}</code></pre> }
export function JsonView({ value }: { value: unknown }) { return <Code>{JSON.stringify(value, null, 2)}</Code> }
export function Metric({ label, value, detail, icon }: { label: string; value: number | string; detail: string; icon?: ReactNode }) { return <div className="metric"><div className="metric-label"><span>{label}</span>{icon && <span className="metric-icon" aria-hidden="true">{icon}</span>}</div><strong>{value}</strong><small>{detail}</small></div> }
export function Table({ headings, children }: { headings: string[]; children: ReactNode }) { return <div className="table-scroll"><table><thead><tr>{headings.map(h => <th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div> }
