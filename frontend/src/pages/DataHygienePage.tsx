import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/endpoints'
import { shortId, statusLabel } from '../lib/format'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Loading,
  PageHeader,
  Panel,
  Table,
} from '../components/ui/primitives'

export function DataHygienePage() {
  const qc = useQueryClient()
  const issues = useQuery({ queryKey: ['hygiene'], queryFn: api.teamOps.hygieneIssues })

  const scan = useMutation({
    mutationFn: api.teamOps.hygieneScan,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hygiene'] }),
  })

  const resolve = useMutation({
    mutationFn: (id: string) => api.teamOps.resolveIssue(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hygiene'] }),
  })

  return (
    <>
      <PageHeader
        title="Data hygiene"
        subtitle="Duplicates, phone formats, missing prices and photos (FR-TEAM-05)."
        actions={
          <Button onClick={() => scan.mutate()} disabled={scan.isPending}>
            Run scan
          </Button>
        }
      />

      <Panel>
        {issues.isLoading ? (
          <Loading />
        ) : issues.isError ? (
          <ErrorBox error={issues.error} />
        ) : !issues.data?.length ? (
          <EmptyState title="No open issues" hint="Run a scan to check for data quality problems." />
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Related</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {issues.data.map((i) => (
                <tr key={i.id}>
                  <td>{statusLabel(i.issue_type)}</td>
                  <td>{shortId(i.related_id)}</td>
                  <td>
                    <Badge tone={i.is_resolved ? 'good' : 'warn'}>
                      {i.is_resolved ? 'resolved' : 'open'}
                    </Badge>
                  </td>
                  <td>
                    {!i.is_resolved ? (
                      <Button size="sm" onClick={() => resolve.mutate(i.id)}>
                        Resolve
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>
    </>
  )
}
