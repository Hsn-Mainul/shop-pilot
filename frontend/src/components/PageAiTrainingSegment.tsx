import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../api/endpoints'
import { useToast } from './ui/ToastProvider'
import type { PageAIProfile } from '../types/api'
import {
  Badge,
  Button,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  Panel,
  Select,
  Table,
  Textarea,
} from './ui/primitives'

const TONE_PRESETS = [
  'Inspiring & Civic',
  'Professional & Articulate',
  'Courteous & Friendly',
  'Empathetic & Purpose-Driven',
  'Authoritative & Informative',
  'Energetic & Promotional',
]

const TYPE_CONFIG: Record<string, { label: string; toneColor: string }> = {
  political_campaign: { label: 'Political Campaign', toneColor: '#818cf8' },
  non_profit: { label: 'Non-Profit / NGO', toneColor: '#34d399' },
  ecommerce: { label: 'E-Commerce Store', toneColor: '#38bdf8' },
  media: { label: 'News & Media', toneColor: '#f59e0b' },
  community: { label: 'Community & Cause', toneColor: '#ec4899' },
  services: { label: 'Professional Services', toneColor: '#a78bfa' },
  creator: { label: 'Creator / Public Figure', toneColor: '#fb7185' },
  general: { label: 'General Organization', toneColor: '#94a3b8' },
}

export function PageAiTrainingSegment({ initialPageId }: { initialPageId?: string }) {
  const qc = useQueryClient()
  const { showToast } = useToast()
  const [selectedPageId, setSelectedPageId] = useState<string>(initialPageId || '')

  // Form state for selected page profile
  const [personaName, setPersonaName] = useState('')
  const [roleDesc, setRoleDesc] = useState('')
  const [tone, setTone] = useState('')
  const [topicsStr, setTopicsStr] = useState('')
  const [instructions, setInstructions] = useState('')
  const [dosDonts, setDosDonts] = useState('')
  const [autoReply, setAutoReply] = useState(true)
  const [includeCatalog, setIncludeCatalog] = useState(false)
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null)

  // New knowledge item state
  const [newKTitle, setNewKTitle] = useState('')
  const [newKContent, setNewKContent] = useState('')
  const [newKCategory, setNewKCategory] = useState('shop_fact')

  // Live simulation chat state
  const [simMessage, setSimMessage] = useState('')
  const [simHistory, setSimHistory] = useState<
    Array<{ sender: 'user' | 'ai'; text: string; persona?: string }>
  >([])

  // Queries
  const pagesQuery = useQuery({
    queryKey: ['page-ai-profiles'],
    queryFn: () => api.pageAi.list(),
  })

  const pages = pagesQuery.data ?? []

  // Auto-select first page if none selected
  useEffect(() => {
    if (!selectedPageId && pages.length > 0) {
      setSelectedPageId(pages[0].page_id)
    }
  }, [pages, selectedPageId])

  const selectedProfile: PageAIProfile | undefined = pages.find((p) => p.page_id === selectedPageId)

  // Populate form state when selected page changes
  useEffect(() => {
    if (selectedProfile) {
      setPersonaName(selectedProfile.ai_persona_name || `${selectedProfile.page_name} Assistant`)
      setRoleDesc(selectedProfile.ai_role_description || '')
      setTone(selectedProfile.tone || 'Inspiring & Civic')
      setTopicsStr((selectedProfile.key_topics || []).join(', '))
      setInstructions(selectedProfile.system_instructions || '')
      setDosDonts(selectedProfile.dos_and_donts || '')
      setAutoReply(selectedProfile.auto_reply_enabled ?? true)
      setIncludeCatalog(selectedProfile.include_product_catalog ?? false)
      setSaveSuccessMsg(null)
    }
  }, [selectedProfile])

  // Page Knowledge Query
  const knowledgeQuery = useQuery({
    queryKey: ['page-ai-knowledge', selectedPageId],
    queryFn: () => api.pageAi.knowledge(selectedPageId),
    enabled: Boolean(selectedPageId),
  })

  // Mutations
  const studyMutation = useMutation({
    mutationFn: (pid: string) => api.pageAi.study(pid),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ['page-ai-profiles'] })
      qc.invalidateQueries({ queryKey: ['page-ai-knowledge', selectedPageId] })
      setSaveSuccessMsg(`✓ Page '${updated.page_name}' was successfully studied with AI!`)
      setTimeout(() => setSaveSuccessMsg(null), 5000)
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not study this page.', 'error')
    },
  })

  const trainFromPostsMutation = useMutation({
    mutationFn: (pid: string) => api.pageAi.trainFromPosts(pid),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['page-ai-knowledge', selectedPageId] })
      showToast(result.message, result.new_facts_learned > 0 ? 'success' : 'info')
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not train from this page\'s posts.', 'error')
    },
  })

  const updateMutation = useMutation({
    mutationFn: () => {
      const topics = topicsStr
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
      return api.pageAi.update(selectedPageId, {
        ai_persona_name: personaName,
        ai_role_description: roleDesc,
        tone,
        key_topics: topics,
        system_instructions: instructions,
        dos_and_donts: dosDonts,
        auto_reply_enabled: autoReply,
        include_product_catalog: includeCatalog,
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['page-ai-profiles'] })
      setSaveSuccessMsg('✓ Page AI configuration saved successfully!')
      setTimeout(() => setSaveSuccessMsg(null), 5000)
    },
  })

  const addKnowledgeMutation = useMutation({
    mutationFn: () =>
      api.pageAi.addKnowledge(selectedPageId, {
        title: newKTitle,
        content: newKContent,
        category: newKCategory,
      }),
    onSuccess: () => {
      setNewKTitle('')
      setNewKContent('')
      qc.invalidateQueries({ queryKey: ['page-ai-knowledge', selectedPageId] })
    },
  })

  const deleteKnowledgeMutation = useMutation({
    mutationFn: (id: string) => api.pageAi.deleteKnowledge(selectedPageId, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['page-ai-knowledge', selectedPageId] })
    },
  })

  const simulateMutation = useMutation({
    mutationFn: (msg: string) => api.pageAi.simulateChat(selectedPageId, msg),
    onSuccess: (data, variables) => {
      setSimHistory((prev) => [
        ...prev,
        { sender: 'user', text: variables },
        { sender: 'ai', text: data.reply, persona: data.persona },
      ])
      setSimMessage('')
    },
  })

  if (pagesQuery.isLoading) return <Loading />
  if (pagesQuery.isError) return <ErrorBox error={pagesQuery.error} />

  if (pages.length === 0) {
    return (
      <EmptyState
        title="No Connected Social Pages Found"
        hint="Connect your Facebook Page or Instagram Business Account in Integrations first. Once connected, you can train and study the AI for each page here."
      />
    )
  }

  const typeMeta = selectedProfile
    ? TYPE_CONFIG[selectedProfile.detected_type] || TYPE_CONFIG.general
    : TYPE_CONFIG.general

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 1. Page Selection Strip */}
      <div
        style={{
          background: 'var(--surface, #1e293b)',
          border: '1px solid var(--border, #334155)',
          borderRadius: '12px',
          padding: '16px 20px',
        }}
      >
        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--muted, #94a3b8)', marginBottom: '12px' }}>
          SELECT INTEGRATED PAGE TO TRAIN & STUDY:
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {pages.map((p) => {
            const isSelected = p.page_id === selectedPageId
            const meta = TYPE_CONFIG[p.detected_type] || TYPE_CONFIG.general
            const isStudied = p.study_status === 'studied'
            return (
              <button
                key={p.page_id}
                onClick={() => setSelectedPageId(p.page_id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '10px 16px',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  border: isSelected ? '2px solid #3b82f6' : '1px solid var(--border, #334155)',
                  background: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'var(--surface-muted, #0f172a)',
                  color: isSelected ? '#ffffff' : 'var(--text-muted, #cbd5e1)',
                  fontWeight: isSelected ? 600 : 500,
                  transition: 'all 0.2s ease',
                }}
              >
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontSize: '14px', fontWeight: 600 }}>{p.page_name}</div>
                  <div style={{ fontSize: '11px', color: 'var(--muted, #94a3b8)', display: 'flex', gap: '6px' }}>
                    <span>{meta.label}</span>
                    <span>•</span>
                    <span style={{ color: isStudied ? '#22c55e' : '#f59e0b' }}>
                      {isStudied ? 'Studied' : 'Pending Study'}
                    </span>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {saveSuccessMsg && (
        <div
          style={{
            background: 'rgba(34, 197, 94, 0.15)',
            border: '1px solid rgba(34, 197, 94, 0.4)',
            color: '#4ade80',
            padding: '12px 18px',
            borderRadius: '10px',
            fontWeight: 500,
          }}
        >
          {saveSuccessMsg}
        </div>
      )}

      {selectedProfile && (
        <>
          {/* 2. Page Study & Intelligence Overview Card */}
          <Panel
            title={`Page AI Profile: ${selectedProfile.page_name}`}
            actions={
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <Badge tone={selectedProfile.study_status === 'studied' ? 'good' : 'warn'}>
                  {selectedProfile.study_status === 'studied'
                    ? `Studied with AI (${typeMeta.label})`
                    : 'Pending AI Study'}
                </Badge>
                <Button
                  variant="secondary"
                  onClick={() => trainFromPostsMutation.mutate(selectedProfile.page_id)}
                  disabled={trainFromPostsMutation.isPending}
                  title="Fetch this page's recent posts and teach the AI any products/prices/policies mentioned in them"
                >
                  {trainFromPostsMutation.isPending ? 'Reading Posts…' : 'Train from Posts'}
                </Button>
                <Button
                  onClick={() => studyMutation.mutate(selectedProfile.page_id)}
                  disabled={studyMutation.isPending}
                >
                  {studyMutation.isPending ? 'Analyzing Page…' : 'Study Page with AI'}
                </Button>
              </div>
            }
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', marginBottom: '16px' }}>
              <div style={{ padding: '12px 16px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', border: '1px solid var(--border, #334155)' }}>
                <div style={{ fontSize: '11px', color: 'var(--muted, #94a3b8)', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Detected Category & Mission
                </div>
                <div style={{ fontSize: '15px', fontWeight: 600, color: typeMeta.toneColor }}>
                  {typeMeta.label}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--muted, #94a3b8)', marginTop: '4px' }}>
                  Platform: {selectedProfile.platform.toUpperCase()}
                </div>
              </div>

              <div style={{ padding: '12px 16px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', border: '1px solid var(--border, #334155)' }}>
                <div style={{ fontSize: '11px', color: 'var(--muted, #94a3b8)', textTransform: 'uppercase', marginBottom: '4px' }}>
                  E-Commerce Catalog Safeguard
                </div>
                <div style={{ fontSize: '15px', fontWeight: 600, color: includeCatalog ? '#38bdf8' : '#22c55e' }}>
                  {includeCatalog ? 'Retail Catalog Active' : 'Catalog Disabled (Non-Commercial)'}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--muted, #94a3b8)', marginTop: '4px' }}>
                  {includeCatalog ? 'Allows AI to quote prices & taking orders' : 'Prevents hallucinating commercial sofas, beds, or delivery charges'}
                </div>
              </div>

              <div style={{ padding: '12px 16px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', border: '1px solid var(--border, #334155)' }}>
                <div style={{ fontSize: '11px', color: 'var(--muted, #94a3b8)', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Last AI Study Analysis
                </div>
                <div style={{ fontSize: '14px', fontWeight: 500 }}>
                  {selectedProfile.last_studied_at
                    ? new Date(selectedProfile.last_studied_at).toLocaleString()
                    : 'Not yet analyzed'}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--muted, #94a3b8)', marginTop: '4px' }}>
                  {selectedProfile.about || selectedProfile.bio || 'Page info extracted via Meta Graph API'}
                </div>
              </div>
            </div>

            {selectedProfile.about && (
              <div style={{ padding: '10px 14px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', fontSize: '13px', color: 'var(--text-muted, #cbd5e1)' }}>
                <strong>About from Page:</strong> {selectedProfile.about}
              </div>
            )}
          </Panel>

          {/* 3. Train Model for this Specific Page (Persona, Directives, Dos & Don'ts) */}
          <Panel title="Train AI Model for this Page (Persona & Guardrails)">
            <p className="muted" style={{ marginBottom: '16px' }}>
              Configure how the AI introduces itself, its tone of voice, key topics, and strict guardrails when customers message this specific page.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                  AI Persona Title / Name
                </label>
                <Input
                  value={personaName}
                  onChange={(e) => setPersonaName(e.target.value)}
                  placeholder="e.g. BallotBuzz Campaign Assistant"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                  Tone of Voice
                </label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <Input
                    value={tone}
                    onChange={(e) => setTone(e.target.value)}
                    placeholder="e.g. Inspiring & Civic"
                  />
                  <Select
                    value=""
                    onChange={(e) => {
                      if (e.target.value) setTone(e.target.value)
                    }}
                    style={{ width: '130px' }}
                  >
                    <option value="">Presets…</option>
                    {TONE_PRESETS.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </Select>
                </div>
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                AI Role & Mission Description
              </label>
              <Input
                value={roleDesc}
                onChange={(e) => setRoleDesc(e.target.value)}
                placeholder="e.g. Official representative for BallotBuzz political campaign and voter guide"
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                Core Topics & Focus Areas (comma-separated)
              </label>
              <Input
                value={topicsStr}
                onChange={(e) => setTopicsStr(e.target.value)}
                placeholder="e.g. Voter Registration, Campaign Platform, Rallies, Volunteer Signups"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                  Custom System Instructions for this Page
                </label>
                <Textarea
                  rows={4}
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="e.g. You are the official representative for BallotBuzz. Answer questions on voting procedures, candidate positions, and community engagement. Always be respectful and non-partisan."
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                  Strict Guardrails: Dos & Don'ts (Hallucination Prevention)
                </label>
                <Textarea
                  rows={4}
                  value={dosDonts}
                  onChange={(e) => setDosDonts(e.target.value)}
                  placeholder="e.g. DO NOT talk about selling products, furniture, sofas, or beds. DO NOT ask for shopping delivery addresses. DO encourage users to check their voter status and attend town halls."
                />
              </div>
            </div>

            {/* Feature & Guardrail Toggles */}
            <div
              style={{
                display: 'flex',
                gap: '24px',
                padding: '14px 18px',
                background: 'rgba(0,0,0,0.2)',
                borderRadius: '10px',
                marginBottom: '20px',
                flexWrap: 'wrap',
              }}
            >
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '14px' }}>
                <input
                  type="checkbox"
                  checked={autoReply}
                  onChange={(e) => setAutoReply(e.target.checked)}
                  style={{ width: '18px', height: '18px' }}
                />
                <span>
                  <strong>Enable AI Autopilot for this Page</strong>
                  <span style={{ display: 'block', fontSize: '12px', color: 'var(--muted, #94a3b8)' }}>
                    AI will automatically answer inbound DMs and comments for {selectedProfile.page_name}
                  </span>
                </span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '14px' }}>
                <input
                  type="checkbox"
                  checked={includeCatalog}
                  onChange={(e) => setIncludeCatalog(e.target.checked)}
                  style={{ width: '18px', height: '18px' }}
                />
                <span>
                  <strong>Include E-Commerce Product Catalog</strong>
                  <span style={{ display: 'block', fontSize: '12px', color: 'var(--muted, #94a3b8)' }}>
                    Only check this if this page sells commercial goods (Leave unchecked for political campaigns or non-profits)
                  </span>
                </span>
              </label>
            </div>

            <Button
              onClick={() => updateMutation.mutate()}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? 'Saving Configuration…' : 'Save Page AI Training Configuration'}
            </Button>
          </Panel>

          {/* 4. Page-Specific Knowledge Base (Taught Facts & FAQs) */}
          <Panel
            title={`Knowledge Base for ${selectedProfile.page_name}`}
            actions={
              <Badge tone="neutral">
                {knowledgeQuery.data?.length ?? 0} Facts/FAQs Taught
              </Badge>
            }
          >
            <p className="muted" style={{ marginBottom: '14px' }}>
              Facts, policies, candidate info, and answers taught specifically for {selectedProfile.page_name}. The AI prioritizes these over general shop facts.
            </p>

            {/* Add new knowledge item form */}
            <div
              style={{
                padding: '16px',
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--border, #334155)',
                borderRadius: '10px',
                marginBottom: '20px',
              }}
            >
              <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '12px' }}>
                + Train AI with a New Fact or Policy for {selectedProfile.page_name}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px', marginBottom: '12px' }}>
                <Input
                  placeholder="Question / Topic (e.g. 'What is the campaign stance on public healthcare?')"
                  value={newKTitle}
                  onChange={(e) => setNewKTitle(e.target.value)}
                />
                <Select value={newKCategory} onChange={(e) => setNewKCategory(e.target.value)}>
                  <option value="shop_fact">Campaign Fact / Info</option>
                  <option value="faq_policy">Policy / FAQ</option>
                  <option value="instruction">Behavior Instruction</option>
                </Select>
              </div>
              <Textarea
                rows={3}
                placeholder="The detailed, verified answer the AI must give..."
                value={newKContent}
                onChange={(e) => setNewKContent(e.target.value)}
                style={{ marginBottom: '12px' }}
              />
              <Button
                onClick={() => addKnowledgeMutation.mutate()}
                disabled={!newKTitle.trim() || !newKContent.trim() || addKnowledgeMutation.isPending}
              >
                {addKnowledgeMutation.isPending ? 'Training Fact…' : 'Train Page AI with this Fact'}
              </Button>
            </div>

            {/* Knowledge Table */}
            {knowledgeQuery.isLoading ? (
              <Loading />
            ) : (knowledgeQuery.data?.length ?? 0) === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px', color: 'var(--muted, #94a3b8)' }}>
                No custom facts taught for this page yet. Click <strong>"⚡ Study Page with AI"</strong> above to auto-generate starter FAQs, or add one using the form above!
              </div>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <th>Topic / Question</th>
                    <th>Category</th>
                    <th>Content Snippet</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(knowledgeQuery.data || []).map((k) => (
                    <tr key={k.id}>
                      <td style={{ fontWeight: 600 }}>{k.title}</td>
                      <td>
                        <Badge tone="neutral">{k.category}</Badge>
                      </td>
                      <td style={{ maxWidth: '380px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {k.content}
                      </td>
                      <td>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => deleteKnowledgeMutation.mutate(k.id)}
                          disabled={deleteKnowledgeMutation.isPending}
                        >
                          Delete
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Panel>

          {/* 5. Live Interactive Chat Simulator for this Page */}
          <Panel title={`Interactive Chat Simulator: Test ${selectedProfile.page_name} AI`}>
            <p className="muted" style={{ marginBottom: '14px' }}>
              Ask questions to verify the AI answers as {personaName} using verified facts without any delusional product or catalog responses!
            </p>

            {/* Chat History Box */}
            <div
              style={{
                minHeight: '180px',
                maxHeight: '320px',
                overflowY: 'auto',
                background: 'rgba(0,0,0,0.3)',
                borderRadius: '10px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                marginBottom: '14px',
                border: '1px solid var(--border, #334155)',
              }}
            >
              {simHistory.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--muted, #94a3b8)', margin: 'auto' }}>
                  Try asking: <em>"What do you offer?"</em>, <em>"How can I participate?"</em>, or <em>"What is your mission?"</em>
                </div>
              ) : (
                simHistory.map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      alignSelf: item.sender === 'user' ? 'flex-end' : 'flex-start',
                      maxWidth: '80%',
                      background: item.sender === 'user' ? '#3b82f6' : 'var(--surface, #1e293b)',
                      color: '#ffffff',
                      padding: '10px 14px',
                      borderRadius: '10px',
                      border: item.sender === 'user' ? 'none' : '1px solid var(--border, #334155)',
                    }}
                  >
                    {item.sender === 'ai' && (
                      <div style={{ fontSize: '11px', color: '#38bdf8', fontWeight: 600, marginBottom: '4px' }}>
                        {item.persona || personaName}
                      </div>
                    )}
                    <div style={{ fontSize: '13px', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
                      {item.text}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Simulator Input */}
            <div style={{ display: 'flex', gap: '10px' }}>
              <Input
                placeholder={`Ask ${selectedProfile.page_name} a test question (e.g. 'What do you offer?' or 'How do I volunteer?')...`}
                value={simMessage}
                onChange={(e) => setSimMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && simMessage.trim() && !simulateMutation.isPending) {
                    simulateMutation.mutate(simMessage)
                  }
                }}
              />
              <Button
                onClick={() => simulateMutation.mutate(simMessage)}
                disabled={!simMessage.trim() || simulateMutation.isPending}
              >
                {simulateMutation.isPending ? 'Generating…' : 'Send Test'}
              </Button>
            </div>
          </Panel>
        </>
      )}
    </div>
  )
}
