import { useState } from 'react'
import { FolderPlus, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAction, useData } from '../api'
import { Empty, ErrorState, Loading, PageTitle, Panel, Success } from '../components/ui'
import { date } from '../lib/date'
import type { Project } from '../types'

export default function Projects() {
  const projects = useData<Project[]>('/projects')
  const action = useAction()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [deleting, setDeleting] = useState<string | null>(null)
  return <><PageTitle eyebrow="WORKSPACE" title="Projects" description="Organize repositories, findings and remediation evidence." /><div className="split-grid form-layout"><Panel title="Create a project"><form className="panel-body" onSubmit={e => { e.preventDefault(); action.mutate({ path: '/projects', body: { name, description } }, { onSuccess: () => { setName(''); setDescription('') } }) }}><label>Project name<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} placeholder="Platform engineering" /></label><label>Description<textarea maxLength={2000} value={description} onChange={e => setDescription(e.target.value)} placeholder="What are you working on?" /></label><button className="button" disabled={action.isPending}><FolderPlus size={16} />{action.isPending ? 'Saving…' : 'Create project'}</button></form></Panel><Panel title="Your projects">{projects.isPending ? <Loading /> : projects.error ? <ErrorState error={projects.error} retry={() => { void projects.refetch() }} /> : !projects.data.length ? <Empty title="No projects yet" detail="Create your first project to connect a repository." /> : <div className="compact-list">{projects.data.map(project => <div className="project-row" key={project.id}><div><Link to={'/repositories?project=' + project.id}><h3>{project.name}</h3></Link><p>{project.description || 'No description'}</p><small>{date(project.created_at)}</small></div><button aria-label={'Delete ' + project.name} className="icon-button" onClick={() => setDeleting(project.id)}><Trash2 size={16} /></button>{deleting === project.id && <div className="delete-confirm"><p>Delete this project, its repositories and stored evidence?</p><button className="button danger" onClick={() => { action.mutate({ path: '/projects/' + project.id, method: 'DELETE' }, { onSuccess: () => setDeleting(null) }) }} disabled={action.isPending}>Delete project</button><button className="button secondary" onClick={() => setDeleting(null)}>Keep project</button></div>}</div>)}</div>}</Panel></div>{action.error && <ErrorState error={action.error} />}{action.isSuccess && <Success>Project changes saved.</Success>}</>
}
