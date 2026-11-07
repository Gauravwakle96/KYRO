import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useAction, useData } from '../api'
import { Badge, Empty, ErrorState, JsonView, Loading, Notice, PageTitle, Panel, Table } from '../components/ui'
import { date } from '../lib/date'
import type { Job, Scan, ScannerHealth } from '../types'

export function Activity() {
  const jobs = useData<Job[]>('/jobs', { poll: 3000 })
  const [selected, setSelected] = useState('')
  const action = useAction()
  const client = useQueryClient()
  const id = selected || jobs.data?.[0]?.id || ''
  const job = jobs.data?.find(j => j.id === id)
  const canRetry = job && ['FAILED', 'CANCELLED', 'INCONCLUSIVE'].includes(job.status) && ['ingest', 'fixture', 'analyze', 'scan', 'enrich'].includes(job.kind)
  const retryLabel = job?.kind === 'ingest' || job?.kind === 'fixture' ? 'Retry import' : job?.kind === 'analyze' ? 'Retry analysis' : job?.kind === 'scan' ? 'Retry scan' : 'Retry enrichment'
  function retrySelected() {
    if (!job || !canRetry) return
    action.mutate({ path: '/jobs/' + job.id + '/retry' }, { onSuccess: result => {
      if (result && typeof result === 'object' && 'id' in result && typeof result.id === 'string') setSelected(result.id)
    } })
  }
  useEffect(() => {
    if (!id) return
    const stream = new EventSource('/api/jobs/' + id + '/events', { withCredentials: true })
    stream.onmessage = event => {
      const data = JSON.parse(event.data) as Job
      client.setQueryData<Job[]>(['/jobs'], old => old?.map(item => item.id === data.id ? data : item))
      if (!['PENDING', 'RUNNING'].includes(data.status)) stream.close()
    }
    stream.onerror = () => stream.close() // Polling above remains the fallback.
    return () => stream.close()
  }, [id, client])
  return <><PageTitle eyebrow="CONTROLLED EXECUTION" title="Agent workspace" description="Actual job events, tool commands, failures and checkpoints." />{action.error && <ErrorState error={action.error} />}{jobs.isPending ? <Loading /> : jobs.error ? <ErrorState error={jobs.error} retry={() => { void jobs.refetch() }} /> : !jobs.data.length ? <Empty title="No execution history" detail="Analyze a repository, run scanners or plan a remediation to start a job." href="/repositories" /> : <div className="split-grid activity-layout"><Panel title="Jobs"><div className="job-list">{jobs.data.map(j => <button className={id === j.id ? 'selected' : ''} key={j.id} data-job-id={j.id} onClick={() => setSelected(j.id)}><div><strong>{j.kind}</strong><small>{date(j.created_at)}</small></div><Badge value={j.status} /></button>)}</div></Panel><Panel title={job ? `${job.kind} · ${job.id.slice(0, 8)}` : 'Execution events'} extra={job && ['RUNNING', 'PENDING'].includes(job.status) ? <button className="button secondary" disabled={action.isPending || job.cancel_requested} onClick={() => action.mutate({ path: '/jobs/' + job.id + '/cancel' })}>{job.cancel_requested ? 'Cancelling…' : 'Cancel job'}</button> : canRetry ? <button className="button secondary" disabled={action.isPending} onClick={retrySelected}>{action.isPending ? 'Queuing retry…' : retryLabel}</button> : undefined}>{job?.payload?.automatic_recovery?.not_before && job.status === 'PENDING' && <Notice>Automatic recovery is scheduled. Attempt {job.payload.automatic_recovery.attempt + 1} of {job.payload.automatic_recovery.max_attempts} starts after {date(job.payload.automatic_recovery.not_before)}. You can cancel this job.</Notice>}{job?.error && <ErrorState error={new Error(job.error)} />}{job?.payload?.automatic_recovery?.history?.length ? <details className="panel-body"><summary>Recovery history · {job.payload.automatic_recovery.history.length} attempt(s)</summary>{job.payload.automatic_recovery.history.map((attempt, index) => <div className="factor" key={index}><div><strong>Attempt {attempt.attempt}</strong><p>{attempt.reason}</p><small>{date(attempt.at)}</small></div></div>)}</details> : null}{job?.events.length ? <div className="timeline">{job.events.map((event, i) => <div className="timeline-item event" key={i}><span className="timeline-dot" /><div><small>{date(event.at)}</small><strong>{event.message}</strong>{event.detail && Object.keys(event.detail).length ? <JsonView value={event.detail} /> : null}</div></div>)}</div> : <p className="panel-body muted">Waiting for the worker to start.</p>}{job && ['ingest', 'fixture', 'analyze', 'scan'].includes(job.kind) && <Link className="button secondary panel-link" to={'/repositories/' + job.resource_id}>Open repository</Link>}{job && ['plan', 'execute', 'verify', 'deliver'].includes(job.kind) && <Link className="button secondary panel-link" to={'/remediation/' + job.resource_id}>Open remediation evidence</Link>}</Panel></div>}</>
}

export function Security() {
  const health = useData<ScannerHealth>('/scanners')
  const scans = useData<Scan[]>('/scans', { poll: 5000 })
  return <><PageTitle eyebrow="SECURITY OPERATIONS" title="Security" description="Sequential, isolated scans with independent execution records." action={<Link className="button" to="/repositories">Choose repository</Link>} /><Panel title="Scanner readiness">{health.isPending ? <Loading label="Checking Docker and scanner versions" /> : health.error ? <ErrorState error={health.error} retry={() => { void health.refetch() }} /> : <div className="scanner-grid">{health.data.scanners.map(scanner => <div className="scanner-item" key={scanner.scanner}><div><h3>{scanner.scanner === 'osv' ? 'OSV-Scanner' : scanner.scanner}</h3><Badge value={scanner.available ? 'AVAILABLE' : 'UNAVAILABLE'} /></div><p className="mono">{scanner.version || scanner.image}</p>{scanner.error && <p>{scanner.error}</p>}</div>)}</div>}{health.data && !health.data.docker.available && <Notice>{health.data.docker.error}. Start Docker before scanning.</Notice>}</Panel><Panel title="Scan history">{scans.isPending ? <Loading /> : scans.error ? <ErrorState error={scans.error} retry={() => { void scans.refetch() }} /> : !scans.data.length ? <Empty title="No scans executed" detail="Open an analyzed repository and run the scanners." href="/repositories" /> : <Table headings={['Scan', 'Purpose', 'Commit', 'Started', 'Outcome']}>{scans.data.map(scan => <tr key={scan.id}><td><Link to={'/security/scans/' + scan.id}>{scan.id.slice(0, 8)}</Link></td><td>{scan.purpose}</td><td className="mono">{scan.snapshot_sha.slice(0, 12)}</td><td>{date(scan.created_at)}</td><td><Badge value={scan.status} /></td></tr>)}</Table>}</Panel></>
}

export function ScanDetails() {
  const { id = '' } = useParams()
  const scan = useData<Scan>('/scans/' + id, { poll: 5000 })
  return <><PageTitle eyebrow="SCANNER EVIDENCE" title={'Scan ' + id.slice(0, 8)} description="Versions, exit codes, diagnostics and structured scanner output." />{scan.isPending ? <Loading /> : scan.error ? <ErrorState error={scan.error} /> : <><Badge value={scan.data.status} />{scan.data.status !== 'SUCCEEDED' && <Notice>This scan has incomplete or failed coverage. Available results do not certify safety.</Notice>}{scan.data.executions?.map(execution => <Panel key={execution.scanner} title={execution.scanner} extra={<Badge value={execution.status} />}><div className="panel-body"><p className="mono">{execution.metadata_json.version}</p><p>Exit {execution.metadata_json.exit_code ?? 'unavailable'} · {execution.metadata_json.duration_seconds ?? 'unavailable'} seconds · {execution.normalized.length} findings</p>{execution.metadata_json.error && (execution.status === 'NOT_APPLICABLE' ? <Notice>{execution.metadata_json.error}</Notice> : <ErrorState error={new Error(execution.metadata_json.error)} />)}<details><summary>Raw execution metadata</summary><JsonView value={execution.metadata_json} /></details><details><summary>Normalized evidence</summary><JsonView value={execution.normalized} /></details></div></Panel>)}</>}</>
}

export function AttackPath() {
  const { id = '' } = useParams()
  const graph = useData<{ nodes: { id: string; type: string; label: string }[]; edges: { source: string; target: string; type: string; evidence: unknown }[]; limitations: string[] }>('/attack-paths/' + id)
  const [selected, setSelected] = useState('')
  const nodes = graph.data?.nodes ?? []
  const position = (index: number) => ({ x: 60 + (index % 3) * 260, y: 55 + Math.floor(index / 3) * 110 })
  return <><PageTitle eyebrow="ATTACK-PATH INTELLIGENCE" title="Evidence graph" description="Inspect recorded relationships. An edge is evidence of a reference, not a proven exploit chain." />{graph.isPending ? <Loading /> : graph.error ? <ErrorState error={graph.error} /> : <><div className="graph-scroll"><svg className="evidence-graph" width="840" height={Math.max(300, Math.ceil(nodes.length / 3) * 110 + 70)} role="img" aria-label="Repository evidence relationship graph">{graph.data.edges.map((edge, i) => { const a = position(nodes.findIndex(n => n.id === edge.source)); const b = position(nodes.findIndex(n => n.id === edge.target)); return <path key={i} d={`M${a.x + 190},${a.y + 30} C${a.x + 240},${a.y + 30} ${b.x - 40},${b.y + 30} ${b.x},${b.y + 30}`} className="graph-edge" /> })}{nodes.map((node, i) => { const p = position(i); return <g key={node.id} transform={`translate(${p.x} ${p.y})`} className={'graph-node ' + (selected === node.id ? 'active' : '')}><rect width="205" height="65" rx="7" /><text x="13" y="23" className="graph-type">{node.type.toUpperCase()}</text><text x="13" y="46">{node.label.length > 26 ? node.label.slice(0, 24) + '…' : node.label}</text></g> })}</svg></div><Panel title="Explore nodes"><div className="node-buttons">{nodes.map(node => <button className={'button secondary ' + (selected === node.id ? 'selected' : '')} key={node.id} onClick={() => setSelected(node.id)}>{node.label}</button>)}</div>{selected && <JsonView value={graph.data.edges.filter(edge => edge.source === selected || edge.target === selected)} />}</Panel><Panel title="Relationship evidence"><Table headings={['Source', 'Relationship', 'Target', 'Evidence']}>{graph.data.edges.map((edge, i) => <tr key={i}><td>{nodes.find(n => n.id === edge.source)?.label}</td><td className="mono">{edge.type}</td><td>{nodes.find(n => n.id === edge.target)?.label}</td><td><details><summary>Inspect</summary><JsonView value={edge.evidence} /></details></td></tr>)}</Table></Panel></>}</>
}
