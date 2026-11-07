import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Check, Eye, EyeOff, Fingerprint, KeyRound, Mail, ShieldCheck, Sparkles } from 'lucide-react'
import { api, setCsrf, useData } from '../api'
import { ErrorState, Loading } from '../components/ui'

function EngineeringOrbit() {
  return <div className="engineering-orbit" aria-hidden="true">
    <svg viewBox="0 0 580 330" className="orbit-art">
      <defs>
        <linearGradient id="kyro-metal" x1="0" y1="0" x2=".7" y2="1">
          <stop offset="0" stopColor="#fffdf6" /><stop offset=".36" stopColor="#d5e2ff" />
          <stop offset=".5" stopColor="#6e83aa" /><stop offset=".68" stopColor="#e9f0ff" /><stop offset="1" stopColor="#95a8c9" />
        </linearGradient>
        <linearGradient id="kyro-orbit" x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="#6fa4ff" stopOpacity=".15" /><stop offset=".5" stopColor="#8fc8ff" /><stop offset="1" stopColor="#75e2bf" stopOpacity=".2" />
        </linearGradient>
        <radialGradient id="kyro-halo"><stop stopColor="#4383e6" stopOpacity=".21" /><stop offset="1" stopColor="#4383e6" stopOpacity="0" /></radialGradient>
      </defs>
      <ellipse cx="290" cy="164" rx="250" ry="150" fill="url(#kyro-halo)" />
      <g className="orbit-rings">
        <ellipse cx="290" cy="164" rx="235" ry="75" transform="rotate(-22 290 164)" fill="none" stroke="url(#kyro-orbit)" strokeWidth="1.3" />
        <ellipse cx="290" cy="164" rx="187" ry="98" transform="rotate(24 290 164)" fill="none" stroke="#7a94bb" strokeOpacity=".32" />
        <ellipse cx="290" cy="164" rx="124" ry="124" fill="none" stroke="#7a94bb" strokeOpacity=".14" strokeDasharray="3 9" />
      </g>
      <g transform="translate(248 107)">
        <path d="M0 0H19V44L61 0H87L37 51L91 111H64L19 61V111H0Z" fill="#243451" transform="translate(6 8)" />
        <path d="M0 0H19V44L61 0H87L37 51L91 111H64L19 61V111H0Z" fill="url(#kyro-metal)" stroke="#d7e5ff" strokeWidth=".6" />
      </g>
      <g className="orbit-points">
        <circle cx="104" cy="96" r="5" fill="#8caeff" /><circle cx="475" cy="231" r="5" fill="#7be4bf" />
        <circle cx="416" cy="101" r="4" fill="#f0cda0" /><circle cx="166" cy="233" r="4" fill="#bba8f5" />
      </g>
      <g fill="#9cacc6" fontFamily="JetBrains Mono, monospace" fontSize="9" letterSpacing="1.3">
        <text x="40" y="72">UNDERSTAND</text><text x="437" y="82">INVESTIGATE</text>
        <text x="98" y="270">ENGINEER</text><text x="437" y="266" fill="#9ee4cb">VERIFY</text>
      </g>
    </svg>
    <div className="orbit-caption"><span />THE KYRO WORKFLOW<span /></div>
  </div>
}

export default function Auth() {
  const setup = useData<{ setup_required: boolean }>('/auth/setup')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const client = useQueryClient()
  const creating = setup.data?.setup_required
  const action = useMutation({ mutationFn: () => api<{ csrf_token: string }>(creating ? '/auth/register' : '/auth/login', 'POST', { email, password }), onSuccess: result => { setCsrf(result.csrf_token); void client.invalidateQueries() } })
  return <div className="auth-page">
    <header className="auth-brand">
      <div className="wordmark"><span className="kyro-symbol">K</span>KYRO</div>
      <span className="auth-brand-divider" /><span className="auth-tagline">Think. Build. Secure.</span>
      <span className="auth-private"><Fingerprint size={15} />Your private engineering workspace</span>
    </header>
    <main className="auth-layout">
      <section className="auth-story" aria-label="About KYRO">
        <div className="auth-kicker"><Sparkles size={14} />BUILT FOR THE WAY YOU BUILD</div>
        <h1>Find the risk.<br /><span>Ship the fix.</span></h1>
        <p>Turn security findings into better software.<br className="desktop-break" /> Understand the code. Make the change. Verify every step.</p>
        <EngineeringOrbit />
        <div className="auth-principles"><span><Check size={14} />Reviewed changes</span><span><Check size={14} />Isolated execution</span><span><Check size={14} />Independent checks</span></div>
      </section>
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-card-top"><span className="auth-card-icon"><Fingerprint size={25} /></span><span className="eyebrow">YOUR WORKSPACE AWAITS</span></div>
        <h2 id="auth-title">{creating ? 'Make it yours.' : 'Welcome back.'}</h2>
        <p>{creating ? 'Create your owner account and start building with KYRO.' : 'Sign in and pick up where you left off.'}</p>
        {setup.isPending ? <Loading label="Checking workspace" /> : setup.error ? <ErrorState error={setup.error} retry={() => { void setup.refetch() }} /> : <form onSubmit={event => { event.preventDefault(); action.mutate() }}>
          <label htmlFor="auth-email">Email<div className="auth-input"><Mail size={17} /><input id="auth-email" type="email" placeholder="you@example.com" autoComplete="username" maxLength={254} required value={email} onChange={e => setEmail(e.target.value)} /></div></label>
          <label htmlFor="auth-password">Password<div className="auth-input"><KeyRound size={17} /><input id="auth-password" type={visible ? 'text' : 'password'} placeholder="Enter your password" minLength={12} maxLength={256} autoComplete={creating ? 'new-password' : 'current-password'} required value={password} onChange={e => setPassword(e.target.value)} /><button type="button" className="password-toggle" aria-label={visible ? 'Hide password' : 'Show password'} aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></label>
          {creating && <small>Choose a password with at least 12 characters.</small>}
          {action.error && <ErrorState error={action.error} />}
          <button className="button auth-submit" disabled={action.isPending}>{action.isPending ? creating ? 'Creating workspace…' : 'Signing in…' : creating ? 'Create workspace' : 'Sign in'}<ArrowRight size={17} /></button>
        </form>}
        <div className="auth-reassurance"><ShieldCheck size={17} /><div>Built around your control.<small>You review the plan. KYRO does the work.</small></div></div>
      </section>
    </main>
    <footer className="auth-footer"><span>ENGINEERING WITH EVIDENCE.</span><span>Think deeper. Build better. Stay secure.</span></footer>
  </div>
}
