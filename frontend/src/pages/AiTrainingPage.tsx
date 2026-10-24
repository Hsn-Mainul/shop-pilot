import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../api/endpoints'
import { useSearchParams } from 'react-router-dom'
import { PageAiTrainingSegment } from '../components/PageAiTrainingSegment'
import { Modal } from '../components/ui/Modal'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  PageHeader,
  Panel,
  Select,
  StatTile,
  Table,
  Textarea,
} from '../components/ui/primitives'

export function AiTrainingPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const tabFromUrl = searchParams.get('tab')
  const initialPageId = searchParams.get('pageId') || undefined
  const [activeTab, setActiveTab] = useState<'pages' | 'general'>(
    tabFromUrl === 'general' ? 'general' : 'pages'
  )

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('shop_fact')
  const [fileRef, setFileRef] = useState('')
  const [uploading, setUploading] = useState(false)

  // RAG Vector Search Playground state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResult, setSearchResult] = useState<any | null>(null)
  const [reindexSuccessMsg, setReindexSuccessMsg] = useState<string | null>(null)
  const [showTeachModal, setShowTeachModal] = useState(false)

  const knowledge = useQuery({ queryKey: ['ai-knowledge'], queryFn: api.ai.knowledge })
  const pending = useQuery({ queryKey: ['ai-pending'], queryFn: api.ai.pending })
  const ragStatus = useQuery({ queryKey: ['ai-rag-status'], queryFn: api.ai.ragStatus })

  const teach = useMutation({
    mutationFn: () =>
      api.ai.teach({
        category,
        title,
        content: content || `Uploaded file: ${fileRef}`,
        source_file_ref: fileRef || undefined,
      }),
    onSuccess: () => {
      setTitle('')
      setContent('')
      setFileRef('')
      setShowTeachModal(false)
      qc.invalidateQueries({ queryKey: ['ai-knowledge'] })
      qc.invalidateQueries({ queryKey: ['ai-pending'] })
      qc.invalidateQueries({ queryKey: ['ai-rag-status'] })
    },
  })

  async function onKnowledgeFile(file: File | null) {
    if (!file) return
    setUploading(true)
    try {
      const res = await api.media.upload(file)
      setFileRef(res.url)
      setCategory('file')
      if (!title) setTitle(file.name)
      if (!content && file.type.startsWith('text/')) {
        setContent(await file.text())
      } else if (!content) {
        setContent(`Knowledge file attached: ${file.name}`)
      }
    } finally {
      setUploading(false)
    }
  }

  const approve = useMutation({
    mutationFn: ({ id, ok }: { id: string; ok: boolean }) => api.ai.approve(id, ok),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-knowledge'] })
      qc.invalidateQueries({ queryKey: ['ai-pending'] })
      qc.invalidateQueries({ queryKey: ['ai-rag-status'] })
    },
  })

  const reindex = useMutation({
    mutationFn: () => api.ai.ragReindex(),
    onSuccess: (data) => {
      setReindexSuccessMsg(data.message)
      qc.invalidateQueries({ queryKey: ['ai-knowledge'] })
      qc.invalidateQueries({ queryKey: ['ai-rag-status'] })
      setTimeout(() => setReindexSuccessMsg(null), 6000)
    },
  })

  const testSearch = useMutation({
    mutationFn: (q: string) => api.ai.ragSearch(q, 5),
    onSuccess: (data) => {
      setSearchResult(data)
    },
  })

  const rag = ragStatus.data

  return (
    <>
      <PageHeader
        title="Train the AI & Social Page Models"
        subtitle="Study connected social pages (e.g. BallotBuzz political campaign), configure specialized AI personas & guardrails, and manage vector knowledge."
        actions={
          activeTab === 'general' ? (
            <div className="row" style={{ gap: '0.5rem' }}>
              <Button
                variant="secondary"
                onClick={() => reindex.mutate()}
                disabled={reindex.isPending}
              >
                {reindex.isPending ? 'Vectorizing…' : 'Re-Vectorize All Knowledge & Catalog'}
              </Button>
              <Button onClick={() => setShowTeachModal(true)}>
                <Plus size={15} style={{ marginRight: 6 }} />
                Teach Something New
              </Button>
            </div>
          ) : undefined
        }
      />

      {/* Segment Tabs Navigation */}
      <div
        style={{
          display: 'flex',
          gap: '12px',
          borderBottom: '1px solid var(--border, #334155)',
          marginBottom: '24px',
          paddingBottom: '12px',
        }}
      >
        <button
          onClick={() => {
            setActiveTab('pages')
            setSearchParams({ tab: 'pages' })
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: activeTab === 'pages' ? '#3b82f6' : 'transparent',
            color: activeTab === 'pages' ? '#ffffff' : 'var(--muted, #94a3b8)',
            border: activeTab === 'pages' ? 'none' : '1px solid var(--border, #334155)',
            padding: '10px 18px',
            borderRadius: '8px',
            fontWeight: 600,
            fontSize: '14px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          Page-Specific AI Training & Study
        </button>

        <button
          onClick={() => {
            setActiveTab('general')
            setSearchParams({ tab: 'general' })
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: activeTab === 'general' ? '#3b82f6' : 'transparent',
            color: activeTab === 'general' ? '#ffffff' : 'var(--muted, #94a3b8)',
            border: activeTab === 'general' ? 'none' : '1px solid var(--border, #334155)',
            padding: '10px 18px',
            borderRadius: '8px',
            fontWeight: 600,
            fontSize: '14px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          Global Knowledge Base & Vector Engine (RAG)
        </button>
      </div>

      {activeTab === 'pages' ? (
        <PageAiTrainingSegment initialPageId={initialPageId} />
      ) : (
        <>
          {reindexSuccessMsg && (
            <div
              style={{
                background: 'rgba(34, 197, 94, 0.15)',
                border: '1px solid rgba(34, 197, 94, 0.4)',
                color: '#4ade80',
                padding: '12px 16px',
                borderRadius: '8px',
                marginBottom: '16px',
              }}
            >
              ✓ {reindexSuccessMsg}
            </div>
          )}

      {/* Ollama & RAG Status Tiles */}
      <div className="stats-grid" style={{ marginBottom: '20px' }}>
        <StatTile
          label="Ollama AI Engine"
          value={
            rag?.ollama_online ? (
              <span style={{ color: '#22c55e', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: '#22c55e',
                    display: 'inline-block',
                  }}
                />
                Online ({rag.ollama_version || 'v0.4+'})
              </span>
            ) : (
              <span style={{ color: '#ef4444' }}>Offline</span>
            )
          }
          hint={rag?.chat_model ? `Chat: ${rag.chat_model}` : 'Model not ready'}
          tone={rag?.ollama_online ? 'good' : 'danger'}
        />

        <StatTile
          label="Embedding Model (RAG)"
          value={rag?.embed_model || 'all-minilm'}
          hint={
            rag?.embed_ready
              ? 'Dense vector generation active'
              : 'Embedding model downloading or ready'
          }
          tone={rag?.embed_ready ? 'good' : 'warn'}
        />

        <StatTile
          label="Vectorized Shop Facts"
          value={`${rag?.knowledge_indexed ?? 0} / ${rag?.knowledge_total ?? 0}`}
          hint={`${
            rag?.knowledge_total
              ? Math.round(((rag.knowledge_indexed || 0) / rag.knowledge_total) * 100)
              : 100
          }% indexed in vector store`}
          tone="default"
        />

        <StatTile
          label="Vectorized Products"
          value={`${rag?.products_indexed ?? 0} / ${rag?.products_total ?? 0}`}
          hint={`${
            rag?.products_total
              ? Math.round(((rag.products_indexed || 0) / rag.products_total) * 100)
              : 100
          }% indexed in catalog RAG`}
          tone="default"
        />
      </div>

      {/* Semantic Vector Search Sandbox */}
      <Panel
        title="Interactive Semantic Vector Search (RAG Sandbox)"
        className="mb-4"
        actions={
          <Badge tone={searchResult?.mode === 'vector' ? 'good' : 'neutral'}>
            Mode: {searchResult?.mode || 'Vector Search'}
          </Badge>
        }
      >
        <p className="muted" style={{ marginBottom: '12px' }}>
          Test how Ollama retrieves relevant shop policies, FAQs, and catalog items for customer queries
          before generating the AI response.
        </p>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
          <Input
            placeholder="e.g., 'What is your delivery fee in Dhaka?' or 'Red panjabi size M stock' or 'Return policy'"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && searchQuery.trim()) {
                testSearch.mutate(searchQuery)
              }
            }}
          />
          <Button
            onClick={() => testSearch.mutate(searchQuery)}
            disabled={!searchQuery.trim() || testSearch.isPending}
          >
            {testSearch.isPending ? 'Searching…' : 'Semantic Search'}
          </Button>
        </div>

        {searchResult && (
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.03)',
              borderRadius: '8px',
              padding: '16px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              {/* Matched Facts */}
              <div>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#94a3b8' }}>
                  MATCHED SHOP KNOWLEDGE ({searchResult.knowledge.length})
                </h4>
                {searchResult.knowledge.length === 0 ? (
                  <div className="muted" style={{ fontSize: '13px' }}>
                    No knowledge items matched.
                  </div>
                ) : (
                  <div className="stack" style={{ gap: '8px' }}>
                    {searchResult.knowledge.map((k: any) => (
                      <div
                        key={k.id}
                        style={{
                          background: 'rgba(255, 255, 255, 0.05)',
                          padding: '10px',
                          borderRadius: '6px',
                          borderLeft: '3px solid #38bdf8',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            marginBottom: '4px',
                          }}
                        >
                          <strong>{k.title}</strong>
                          <Badge tone="info">{Math.round(k.similarity * 100)}% match</Badge>
                        </div>
                        <div style={{ fontSize: '12px', color: '#cbd5e1' }}>{k.content}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Matched Products */}
              <div>
                <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#94a3b8' }}>
                  MATCHED CATALOG PRODUCTS ({searchResult.products.length})
                </h4>
                {searchResult.products.length === 0 ? (
                  <div className="muted" style={{ fontSize: '13px' }}>
                    No catalog products matched.
                  </div>
                ) : (
                  <div className="stack" style={{ gap: '8px' }}>
                    {searchResult.products.map((p: any) => (
                      <div
                        key={p.id}
                        style={{
                          background: 'rgba(255, 255, 255, 0.05)',
                          padding: '10px',
                          borderRadius: '6px',
                          borderLeft: '3px solid #22c55e',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            marginBottom: '4px',
                          }}
                        >
                          <strong>{p.name}</strong>
                          <Badge tone="good">{Math.round(p.similarity * 100)}% match</Badge>
                        </div>
                        <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                          Price: {p.price} BDT {p.category ? `• Category: ${p.category}` : ''}
                        </div>
                        <div style={{ fontSize: '12px', color: '#cbd5e1', marginTop: '4px' }}>
                          {p.text_summary}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </Panel>

      <div className="grid-2">
        <Panel title="Approved Knowledge Base">
          {knowledge.isLoading ? (
            <Loading />
          ) : knowledge.isError ? (
            <ErrorBox error={knowledge.error} />
          ) : !knowledge.data?.length ? (
            <EmptyState title="No approved knowledge yet" />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Category</th>
                  <th>Vector Status</th>
                  <th>Content</th>
                </tr>
              </thead>
              <tbody>
                {knowledge.data.map((k) => (
                  <tr key={k.id}>
                    <td>
                      <strong>{k.title}</strong>
                    </td>
                    <td>
                      <Badge>{k.category}</Badge>
                    </td>
                    <td>
                      {k.has_embedding ? (
                        <Badge tone="good">✓ Vectorized</Badge>
                      ) : (
                        <Badge tone="warn">Needs Sync</Badge>
                      )}
                    </td>
                    <td>{k.content.slice(0, 100)}…</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

        <Panel title="Pending Approval">
          {!pending.data?.length ? (
            <EmptyState title="Nothing pending" hint="Inferred facts from chats appear here" />
          ) : (
            <div className="stack">
              {pending.data.map((k) => (
                <div key={k.id} className="row" style={{ justifyContent: 'space-between' }}>
                  <div>
                    <strong>{k.title}</strong>
                    <div className="muted">{k.content.slice(0, 80)}</div>
                  </div>
                  <div className="row">
                    <Button size="sm" onClick={() => approve.mutate({ id: k.id, ok: true })}>
                      Approve & Vectorize
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => approve.mutate({ id: k.id, ok: false })}
                    >
                      Reject
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Modal open={showTeachModal} title="Teach Something New" onClose={() => setShowTeachModal(false)}>
        <div className="stack">
          <label className="field-label">
            Category
            <Select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="shop_fact">Shop fact</option>
              <option value="faq_policy">FAQ / policy</option>
              <option value="instruction">Instruction</option>
              <option value="file">File</option>
            </Select>
          </label>
          <label className="field-label">
            Title
            <Input
              value={title}
              placeholder="e.g., Return Policy or Friday Operating Hours"
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="field-label">
            Content
            <Textarea
              value={content}
              placeholder="Explain the fact in natural detail so the vector engine can match variations..."
              onChange={(e) => setContent(e.target.value)}
              rows={5}
            />
          </label>
          <label className="field-label">
            Upload knowledge file
            <Input
              type="file"
              accept=".txt,.csv,.pdf,image/*,.md"
              onChange={(e) => onKnowledgeFile(e.target.files?.[0] ?? null)}
            />
          </label>
          {uploading ? <div className="muted">Uploading…</div> : null}
          {fileRef ? <div className="muted">Attached: {fileRef}</div> : null}
          {teach.isError ? <ErrorBox error={teach.error} /> : null}
          <Button
            onClick={() => teach.mutate()}
            disabled={!title || (!content && !fileRef) || teach.isPending}
          >
            {teach.isPending ? 'Vectorizing & Saving…' : 'Teach & Vectorize'}
          </Button>
        </div>
      </Modal>
        </>
      )}
    </>
  )
}
