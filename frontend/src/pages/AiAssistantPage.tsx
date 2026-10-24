import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/endpoints'
import { Button, ErrorBox, PageHeader, Panel, Textarea } from '../components/ui/primitives'

export function AiAssistantPage() {
  const [question, setQuestion] = useState('')
  const ask = useMutation({
    mutationFn: () => api.ai.ask(question),
  })
  const simulate = useMutation({
    mutationFn: () => api.ai.simulateChat(question),
  })

  return (
    <>
      <PageHeader
        title="AI assistant"
        subtitle="Ask natural-language questions about this shop’s live data (FR-AI-01)."
      />

      <Panel title="Ask the shop assistant">
        <div className="stack">
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            placeholder="How many orders are waiting to pack? What is low in stock?"
          />
          <div className="row">
            <Button onClick={() => ask.mutate()} disabled={!question.trim() || ask.isPending}>
              Ask
            </Button>
            <Button
              variant="secondary"
              onClick={() => simulate.mutate()}
              disabled={!question.trim() || simulate.isPending}
            >
              Simulate chat reply
            </Button>
          </div>
          {ask.isError ? <ErrorBox error={ask.error} /> : null}
          {ask.data ? (
            <div className="demo-hint">
              <strong>Answer</strong>
              <p>{ask.data.answer}</p>
            </div>
          ) : null}
          {simulate.data ? (
            <div className="demo-hint">
              <strong>Simulated reply</strong>
              <p>{simulate.data.reply}</p>
              <div className="muted">{simulate.data.note}</div>
            </div>
          ) : null}
        </div>
      </Panel>
    </>
  )
}
