import { Link } from 'react-router-dom'
import { Icon } from '../components/Icon'
import { Card, PageHeader } from '../components/ui'
import { PLANNED } from '../lib/plannedModules'
import { useWorkspace } from '../state/workspace'

export function PlannedPage({ id }: { id: keyof typeof PLANNED }) {
  const m = PLANNED[id]
  const { health } = useWorkspace()
  const status = health?.modules[m.module]
  const step = status?.split(':')[1]
  return (
    <>
      <PageHeader title={m.title} subtitle={m.summary} />
      <div className="alert alert-info" role="status">
        <Icon name="info" />
        <div>
          <strong>Module non encore implémenté{step ? ` — prévu à l'étape ${step}` : ''}</strong>
          <p>
            Cet écran ne présente aucun résultat : rien n'est simulé tant que le module n'est pas
            livré et testé. Commencez par <Link to="/import">importer et qualifier un dataset</Link>.
          </p>
        </div>
      </div>
      <div className="grid-2">
        <Card title="Ce qui sera livré" icon={m.icon}>
          <ul className="bullets">
            {m.deliverables.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </Card>
        <Card title="Garde-fous prévus" icon="lock">
          <ul className="bullets">
            {m.safeguards.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  )
}
