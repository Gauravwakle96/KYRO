import { Fragment, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Activity as ActivityIcon, BarChart3, Bot, Boxes, ChevronRight, Cpu, FolderKanban, GitBranch, GitPullRequest, LayoutDashboard, LogOut, Menu, SearchCheck, Settings as SettingsIcon, Shield, ShieldCheck, Sparkles, X } from 'lucide-react'
import { ApiError, setCsrf, useAction, useData } from '../api'
import { ErrorState, Loading } from '../components/ui'
import Auth from '../pages/Auth'
import Overview from '../pages/Overview'
import Projects from '../pages/Projects'
import { Repositories, RepositoryDetails } from '../pages/Repositories'
import { Dependencies, FindingDetails, Findings } from '../pages/Findings'
import { RemediationDetails, RemediationList } from '../pages/Remediation'
import { Activity, AttackPath, ScanDetails, Security } from '../pages/Activity'
import { AnalyticsPage, Models, Onboarding, PullRequests, Settings } from '../pages/System'
import type { Job } from '../types'

const navigation = [
  { to: '/', label: 'Overview', icon: LayoutDashboard }, { to: '/projects', label: 'Projects', icon: FolderKanban },
  { to: '/repositories', label: 'Repositories', icon: GitBranch }, { to: '/security', label: 'Security', icon: Shield, group: 'INTELLIGENCE' },
  { to: '/findings', label: 'Findings', icon: SearchCheck }, { to: '/dependencies', label: 'Dependencies', icon: Boxes },
  { to: '/remediation', label: 'Remediation', icon: Sparkles, group: 'ENGINEERING' }, { to: '/agent-workspace', label: 'Agent Workspace', icon: Bot },
  { to: '/verification', label: 'Verification', icon: ShieldCheck }, { to: '/pull-requests', label: 'Pull Requests', icon: GitPullRequest },
  { to: '/analytics', label: 'Analytics', icon: BarChart3, group: 'CONTROL' }, { to: '/models', label: 'AI Models', icon: Cpu },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

function Workspace({ email }: { email: string }) {
  const [open, setOpen] = useState(false)
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width:960px)').matches)
  const location = useLocation()
  const action = useAction()
  const jobs = useData<Job[]>('/jobs', { poll: 3000 })
  const client = useQueryClient()
  const previous = useRef('')
  const sidebar = useRef<HTMLElement>(null)
  const menu = useRef<HTMLButtonElement>(null)
  const stamp = jobs.data?.map(j => j.id + j.status).join('|') ?? ''
  useEffect(() => {
    const media = window.matchMedia('(max-width:960px)')
    const update = () => setMobile(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  useEffect(() => {
    if (stamp && previous.current && stamp !== previous.current) {
      for (const path of ['/analytics', '/repositories', '/findings', '/scans', '/remediation']) void client.invalidateQueries({ queryKey: [path] })
    }
    previous.current = stamp
  }, [stamp, client])
  useEffect(() => {
    if (!open) return
    const links = sidebar.current?.querySelectorAll<HTMLAnchorElement | HTMLButtonElement>('a, button')
    links?.[0]?.focus()
    function keyboard(event: KeyboardEvent) {
      if (event.key === 'Escape') { setOpen(false); menu.current?.focus() }
      if (event.key === 'Tab' && links?.length) {
        const first = links[0], last = links[links.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    window.addEventListener('keydown', keyboard)
    return () => window.removeEventListener('keydown', keyboard)
  }, [open])
  const label = navigation.find(n => n.to !== '/' && location.pathname.startsWith(n.to))?.label ?? (location.pathname === '/onboarding' ? 'Setup' : 'Overview')
  const running = jobs.data?.filter(j => ['PENDING', 'RUNNING'].includes(j.status)).length ?? 0
  return <div className="workspace"><a href="#main-content" className="skip-link">Skip to content</a>{open && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}<aside className={'sidebar ' + (open ? 'open' : '')} ref={sidebar} inert={mobile && !open}><div className="sidebar-brand"><NavLink to="/" className="wordmark" onClick={() => setOpen(false)}><span className="kyro-symbol">K</span>KYRO</NavLink><button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => { setOpen(false); menu.current?.focus() }}><X size={20} /></button></div><div className="workspace-chip"><span className="avatar">K</span><div>Local workspace<small>PERSONAL</small></div></div><nav aria-label="Main navigation">{navigation.map(({ to, label, icon: Icon, group }) => <Fragment key={to}>{group && <div className="nav-group-label">{group}</div>}<NavLink to={to} end={to === '/'} onClick={() => setOpen(false)}><Icon size={17} /><span>{label}</span></NavLink></Fragment>)}</nav><div className="sidebar-bottom"><NavLink to="/onboarding"><ActivityIcon size={16} />Workspace setup<ChevronRight size={14} /></NavLink><div className="local-mode"><span />LOCAL FIRST <small>v0.1</small></div><small>Think. Build. Secure.</small></div></aside><div className="app-body"><header className="topbar"><div><button ref={menu} className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(true)}><Menu size={20} /></button><span className="breadcrumb">Workspace<ChevronRight size={13} /><strong>{label}</strong></span></div><div className="topbar-right"><NavLink to="/agent-workspace" className="activity-chip"><span className={running ? 'live-dot' : 'idle-dot'} />{running ? `${running} active ${running === 1 ? 'job' : 'jobs'}` : 'No active jobs'}</NavLink><span className="user-avatar" aria-hidden="true">{email.slice(0, 1).toUpperCase()}</span><span className="user-email" title={email}>{email}</span><button aria-label="Sign out" className="icon-button" disabled={action.isPending} onClick={() => { action.mutate({ path: '/auth/logout' }, { onSuccess: () => { setCsrf(''); client.clear(); window.location.assign('/') } }) }}><LogOut size={17} /></button></div></header><main id="main-content" tabIndex={-1}>{action.error && <ErrorState error={action.error} />}<Routes><Route path="/" element={<Overview />} /><Route path="/onboarding" element={<Onboarding />} /><Route path="/projects" element={<Projects />} /><Route path="/repositories" element={<Repositories />} /><Route path="/repositories/:id" element={<RepositoryDetails />} /><Route path="/security" element={<Security />} /><Route path="/security/scans/:id" element={<ScanDetails />} /><Route path="/findings" element={<Findings />} /><Route path="/findings/:id" element={<FindingDetails />} /><Route path="/dependencies" element={<Dependencies />} /><Route path="/attack-paths/:id" element={<AttackPath />} /><Route path="/remediation" element={<RemediationList />} /><Route path="/remediation/:id" element={<RemediationDetails />} /><Route path="/agent-workspace" element={<Activity />} /><Route path="/verification" element={<RemediationList verification />} /><Route path="/pull-requests" element={<PullRequests />} /><Route path="/analytics" element={<AnalyticsPage />} /><Route path="/models" element={<Models />} /><Route path="/settings" element={<Settings />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes><footer className="app-footer"><span>KYRO / Think. Build. Secure.</span><span>Evidence before confidence.</span></footer></main></div></div>
}

export default function App() {
  const auth = useData<{ user: { email: string }; csrf_token: string }>('/auth/me')
  useEffect(() => { if (auth.data) setCsrf(auth.data.csrf_token) }, [auth.data])
  if (auth.isPending) return <div className="boot"><Loading /></div>
  if (auth.error) return auth.error instanceof ApiError && auth.error.status === 401 ? <Auth /> : <div className="boot"><ErrorState error={auth.error} retry={() => { void auth.refetch() }} /></div>
  return <Workspace email={auth.data.user.email} />
}
