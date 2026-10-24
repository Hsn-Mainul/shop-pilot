import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect, type ReactNode } from 'react'
import {
  LayoutGrid,
  Plus,
  Sparkles,
  Hash,
  Send,
  Tag,
  MessageCircle,
  Pencil,
  Trash2,
} from 'lucide-react'
import { api } from '../api/endpoints'
import { API_BASE } from '../api/client'
import type { SocialPost } from '../types/api'
import { shortId } from '../lib/format'
import { useLocale } from '../i18n/LocaleContext'
import {
  Button,
  EmptyState,
  ErrorBox,
  Input,
  Loading,
  PageHeader,
  Select,
  Textarea,
} from '../components/ui/primitives'
import { useToast } from '../components/ui/ToastProvider'
import './SocialStudioPage.css'

type SocialChannel = 'facebook' | 'instagram' | 'tiktok'

function resolveMediaUrl(url: string): string {
  if (!url) return ''
  if (
    url.startsWith('blob:') ||
    url.startsWith('data:') ||
    url.startsWith('http://') ||
    url.startsWith('https://')
  ) {
    return url
  }
  const origin = API_BASE.replace(/\/api\/v1\/?$/, '')
  return `${origin}${url.startsWith('/') ? url : `/${url}`}`
}

export function SocialStudioPage() {
  const { t, locale } = useLocale()
  const qc = useQueryClient()
  const { showToast } = useToast()
  const postLanguage = locale === 'bn' ? 'Bangla (বাংলা)' : 'English'
  const [channels, setChannels] = useState<SocialChannel[]>(['facebook'])
  const [selectedPageId, setSelectedPageId] = useState<string>('')
  const [caption, setCaption] = useState('')
  const [hashtags, setHashtags] = useState('')
  const [firstComment, setFirstComment] = useState('')
  const [photoUrls, setPhotoUrls] = useState<string[]>([])
  const [previewSrcs, setPreviewSrcs] = useState<string[]>([])
  const [productId, setProductId] = useState('')
  const [uploading, setUploading] = useState(false)
  const [showComposer, setShowComposer] = useState(false)
  const [editingPostId, setEditingPostId] = useState<string | null>(null)

  const posts = useQuery({ queryKey: ['social-posts'], queryFn: api.social.list })
  const products = useQuery({
    queryKey: ['products', 'product'],
    queryFn: () => api.products.list(undefined, 'product'),
  })
  const integrations = useQuery({ queryKey: ['integrations'], queryFn: () => api.integrations.list() })
  const pagesQuery = useQuery({ queryKey: ['page-ai-profiles'], queryFn: () => api.pageAi.list() })

  // Extract all connected Facebook pages dynamically
  const fbIntegrations = (integrations.data ?? []).filter(
    (i) => i.provider === 'facebook' && i.status === 'connected'
  )
  const fbPages: Array<{ id: string; name: string; category?: string }> = []
  const seenPageIds = new Set<string>()

  for (const p of pagesQuery.data ?? []) {
    if (p.platform === 'facebook' && !seenPageIds.has(p.page_id)) {
      seenPageIds.add(p.page_id)
      fbPages.push({
        id: p.page_id,
        name: p.page_name,
        category: p.page_category || 'Facebook Page',
      })
    }
  }

  for (const integ of fbIntegrations) {
    const cfg = (integ.config || {}) as {
      page_id?: string
      page_name?: string
      pages?: Array<{ id: string; name: string; category?: string }>
    }
    if (cfg.page_id && !seenPageIds.has(cfg.page_id)) {
      seenPageIds.add(cfg.page_id)
      fbPages.push({
        id: cfg.page_id,
        name: cfg.page_name || 'Facebook Page',
        category: 'Facebook Page',
      })
    }
    for (const p of cfg.pages || []) {
      if (p.id && !seenPageIds.has(p.id)) {
        seenPageIds.add(p.id)
        fbPages.push({
          id: p.id,
          name: p.name || 'Facebook Page',
          category: p.category || 'Facebook Page',
        })
      }
    }
  }

  useEffect(() => {
    if (!selectedPageId && fbPages.length > 0) {
      setSelectedPageId(fbPages[0].id)
    }
  }, [fbPages, selectedPageId])

  const targetFbPage = fbPages.find((p) => p.id === selectedPageId) || fbPages[0]
  const wantsFacebook = channels.includes('facebook')

  function toggleChannel(c: SocialChannel) {
    setChannels((prev) => {
      if (prev.includes(c)) {
        if (prev.length === 1) return prev
        return prev.filter((x) => x !== c)
      }
      return [...prev, c]
    })
  }

  const create = useMutation({
    mutationFn: async () => {
      const hashtagsList = hashtags
        .split(/[\s,]+/)
        .map((h) => h.replace(/^#/, ''))
        .filter(Boolean)
      const shared = {
        photo_urls: photoUrls,
        caption: caption || undefined,
        hashtags: hashtagsList,
        first_comment: firstComment || undefined,
        tagged_product_id: productId || undefined,
        send_price_to_inbox: Boolean(productId),
      }

      if (editingPostId) {
        const channel = channels[0]
        return [
          await api.social.update(editingPostId, {
            ...shared,
            channel,
            page_id:
              channel === 'facebook' ? selectedPageId || targetFbPage?.id || undefined : undefined,
            page_name: channel === 'facebook' ? targetFbPage?.name || undefined : undefined,
          }),
        ]
      }

      const results = []
      for (const channel of channels) {
        results.push(
          await api.social.create({
            ...shared,
            channel,
            page_id:
              channel === 'facebook' ? selectedPageId || targetFbPage?.id || undefined : undefined,
            page_name: channel === 'facebook' ? targetFbPage?.name || undefined : undefined,
          }),
        )
      }
      return results
    },
    onSuccess: () => {
      showToast(editingPostId ? 'Post updated successfully.' : 'Post saved as draft.', 'success')
      resetComposer()
      setShowComposer(false)
      qc.invalidateQueries({ queryKey: ['social-posts'] })
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not save this post.', 'error')
    },
  })

  function resetComposer() {
    setCaption('')
    setHashtags('')
    setFirstComment('')
    setPhotoUrls([])
    previewSrcs.forEach((src) => src.startsWith('blob:') && URL.revokeObjectURL(src))
    setPreviewSrcs([])
    setProductId('')
    setEditingPostId(null)
    setChannels(['facebook'])
  }

  function startEdit(post: SocialPost) {
    setEditingPostId(post.id)
    setChannels([(post.channel as SocialChannel) || 'facebook'])
    setSelectedPageId(post.page_id || '')
    setCaption(post.caption || '')
    setHashtags((post.hashtags || []).join(' '))
    setFirstComment(post.first_comment || '')
    setPhotoUrls(post.photo_urls || [])
    setPreviewSrcs([])
    setProductId(post.tagged_product_id ?? '')
    setShowComposer(true)
  }

  function removePhoto(index: number) {
    setPhotoUrls((prev) => prev.filter((_, i) => i !== index))
    setPreviewSrcs((prev) => {
      const src = prev[index]
      if (src?.startsWith('blob:')) URL.revokeObjectURL(src)
      return prev.filter((_, i) => i !== index)
    })
  }

  const publish = useMutation({
    mutationFn: (id: string) => api.social.publish(id),
    onSuccess: (updated) => {
      if (updated.status === 'failed') {
        showToast(updated.error_message || 'Facebook rejected this post.', 'error')
      } else {
        showToast('Post is publishing to Facebook…', 'success')
      }
      qc.invalidateQueries({ queryKey: ['social-posts'] })
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not publish this post.', 'error')
    },
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.social.delete(id),
    onSuccess: () => {
      showToast('Post deleted.', 'success')
      qc.invalidateQueries({ queryKey: ['social-posts'] })
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not delete this post.', 'error')
    },
  })

  async function onPhotoFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    const fileArr = Array.from(files)
    const localPreviews = fileArr.map((f) => URL.createObjectURL(f))
    setPreviewSrcs((prev) => [...prev, ...localPreviews])
    setUploading(true)
    try {
      let uploadedCount = 0
      for (const file of fileArr) {
        const res = await api.media.upload(file)
        setPhotoUrls((prev) => [...prev, res.url])
        uploadedCount += 1
      }
      showToast(
        uploadedCount > 1 ? `${uploadedCount} photos uploaded.` : 'Photo uploaded.',
        'success',
      )
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Photo upload failed.', 'error')
    } finally {
      setUploading(false)
    }
  }

  const aiHelp = useMutation({
    mutationFn: async (kind: 'caption' | 'hashtags' | 'best_time') => {
      const langRule =
        locale === 'bn'
          ? 'Write entirely in Bangla (বাংলা script). Do not use English except for brand names.'
          : 'Write entirely in English.'

      if (kind === 'best_time') {
        const prompt = `${langRule} Suggest the best time of day to publish on Facebook, Instagram, and TikTok for high engagement. One sentence.`
        return api.ai.ask(prompt).then((r) => r.answer)
      }

      // Caption/hashtags: let the AI actually look at the attached photo and
      // match this page's own persona/tone, instead of guessing from a
      // one-line text prompt with no idea what the image shows.
      const selectedProduct = products.data?.find((p) => p.id === productId)
      const result = await api.ai.socialCaption({
        kind,
        language: locale === 'bn' ? 'bn' : 'en',
        page_id: channels.includes('facebook') ? selectedPageId || targetFbPage?.id : undefined,
        product_id: productId || undefined,
        photo_url: photoUrls[0] || undefined,
        context: !selectedProduct && caption ? caption : undefined,
      })
      return result.answer
    },
    onSuccess: (answer, kind) => {
      if (kind === 'caption') setCaption(answer)
      if (kind === 'hashtags') setHashtags(answer.replace(/#/g, ''))
      if (kind === 'best_time') setFirstComment((c) => c || answer)
    },
  })

  const channelIcons: Record<string, () => ReactNode> = {
    facebook: () => (
      <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
        <circle cx="20" cy="20" r="18" fill="#1877F2" />
        <path
          d="M22.5 21H25.5L26 17H22.5V14.8C22.5 13.8 22.9 13 24.3 13H26V9.4C25.4 9.3 24.3 9.2 23.1 9.2C19.7 9.2 17.5 11.2 17.5 15.2V17H14V21H17.5V31H22.5V21Z"
          fill="white"
        />
      </svg>
    ),
    instagram: () => (
      <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
        <defs>
          <radialGradient id="igPostGrad" cx="30%" cy="107%" r="130%">
            <stop offset="0%" stopColor="#fdf497" />
            <stop offset="45%" stopColor="#fd5949" />
            <stop offset="90%" stopColor="#285AEB" />
          </radialGradient>
        </defs>
        <rect x="3" y="3" width="34" height="34" rx="10" fill="url(#igPostGrad)" />
        <rect x="8.5" y="8.5" width="23" height="23" rx="6.5" stroke="white" strokeWidth="2.2" fill="none" />
        <circle cx="20" cy="20" r="5.5" stroke="white" strokeWidth="2.2" fill="none" />
      </svg>
    ),
    tiktok: () => (
      <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
        <rect x="2" y="2" width="36" height="36" rx="18" fill="#000000" />
        <g transform="translate(4, 4)">
          <path d="M22 13.5C20.7 13.2 19.7 12.2 19.4 10.8H16.5V19.3C16.3 20.6 15.2 21.6 13.7 21.6C12.2 21.6 10.9 20.3 10.9 18.7C10.9 17.2 12.2 15.9 13.7 15.9V13.2C10.5 13.2 8 15.7 8 18.8C8 22 10.5 24.5 13.7 24.5C16.9 24.5 19.5 22 19.5 18.8V14.6C20.7 15.5 22.3 16 24 16V13.2C23.2 13.2 22.5 13 22 13.5Z" fill="#00F2FE" />
          <path d="M21.7 13.2C20.4 12.9 19.4 11.9 19.1 10.5H16.8V19C16.6 20.3 15.5 21.3 14 21.3C12.5 21.3 11.2 20 11.2 18.4C11.2 16.9 12.5 15.6 14 15.6V13.4C10.8 13.4 8.3 15.9 8.3 19.1C8.3 22.3 10.8 24.8 14 24.8C17.2 24.8 19.8 22.3 19.8 19.1V14.3C21 15.2 22.6 15.7 24.3 15.7V13.4C23.5 13.4 22.4 13 21.7 13.2Z" fill="#FE2C55" />
          <path d="M21.4 12.9C20.1 12.6 19.1 11.6 18.8 10.2H17.1V18.7C16.9 20 15.8 21 14.3 21C12.8 21 11.5 19.7 11.5 18.1C11.5 16.6 12.8 15.3 14.3 15.3V13.6C11.1 13.6 8.6 16.1 8.6 19.4C8.6 22.6 11.1 25.1 14.3 25.1C17.5 25.1 20.1 22.6 20.1 19.4V14C21.3 14.9 22.9 15.4 24.6 15.4V13.6C23.8 13.6 22.1 12.7 21.4 12.9Z" fill="#FFFFFF" />
        </g>
      </svg>
    ),
  }

  const postList = posts.data ?? []

  const igConnected = integrations.data?.some((i) => i.provider === 'instagram' && i.status === 'connected')
  const tiktokConnected = integrations.data?.some((i) => i.provider === 'tiktok' && i.status === 'connected')

  return (
    <>
      <PageHeader
        title={t('social')}
        subtitle="Compose shoppable posts, auto-generate captions with AI, and publish to Facebook, Instagram & TikTok."
        actions={
          <Button onClick={() => setShowComposer((v) => !v)}>
            <Plus size={16} />
            <span>{showComposer ? 'Close Composer' : 'Create New Post'}</span>
          </Button>
        }
      />

      {/* Connected Channel Presence Indicators */}
      <div className="social-presence-grid">
        {fbPages.length > 0 ? (
          fbPages.map((page) => (
            <div key={page.id} className="social-presence-card">
              <div className="social-presence-item">
                {channelIcons.facebook()}
                <div>
                  <div className="social-presence-title">{page.name}</div>
                  <div className="social-presence-sub">Facebook • ID: {page.id}</div>
                </div>
              </div>
              <div className="channel-status-pill-active">
                <span className="channel-status-active-dot" />
                <span>Active</span>
              </div>
            </div>
          ))
        ) : (
          <div className="social-presence-card">
            <div className="social-presence-item">
              {channelIcons.facebook()}
              <div>
                <div className="social-presence-title">Facebook Page</div>
                <div className="social-presence-sub">No Connected Pages</div>
              </div>
            </div>
            <div className="channel-status-pill-active channel-status-pill-amber">
              <span className="channel-status-active-dot amber" />
              <span>Offline</span>
            </div>
          </div>
        )}

        <div className="social-presence-card instagram">
          <div className="social-presence-item">
            {channelIcons.instagram()}
            <div>
              <div className="social-presence-title">Instagram</div>
              <div className="social-presence-sub">Direct & Grid Sync</div>
            </div>
          </div>
          <div className="channel-status-pill-active">
            <span className="channel-status-active-dot" />
            <span>{igConnected ? 'Active' : 'Ready'}</span>
          </div>
        </div>

        <div className="social-presence-card tiktok">
          <div className="social-presence-item">
            {channelIcons.tiktok()}
            <div>
              <div className="social-presence-title">TikTok Shop</div>
              <div className="social-presence-sub">Product Videos & DMs</div>
            </div>
          </div>
          <div className="channel-status-pill-active">
            <span className="channel-status-active-dot" />
            <span>{tiktokConnected ? 'Active' : 'Ready'}</span>
          </div>
        </div>
      </div>

      {/* Composer Card (Visible on toggle or inline) */}
      {showComposer && (
        <div className="channel-card-modern social-composer-card">
          <div className="social-composer-header">
            <div className="social-composer-title-group">
              <div className="channels-title-icon">
                <Plus size={20} strokeWidth={2.4} />
              </div>
              <h3 className="social-composer-title">
                {editingPostId ? 'Edit Post' : 'Compose Multi-Channel Post'}
              </h3>
            </div>
            <div className="live-sync-pill">
              <span className="live-sync-dot" />
              <span>AI Co-Pilot Enabled</span>
            </div>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              create.mutate()
            }}
            className="stack social-composer-form"
          >
            {/* Multi-channel selection */}
            <div>
              <label className="field-label social-field-label-gap">
                Target Channels (select one or more)
              </label>
              <div className="social-channel-pills">
                {(['facebook', 'instagram', 'tiktok'] as const).map((c) => {
                  const selected = channels.includes(c)
                  const connected =
                    c === 'facebook'
                      ? fbPages.length > 0
                      : c === 'instagram'
                        ? Boolean(igConnected)
                        : Boolean(tiktokConnected)
                  return (
                    <button
                      key={c}
                      type="button"
                      onClick={() => toggleChannel(c)}
                      disabled={Boolean(editingPostId)}
                      className={`social-channel-pill ${selected ? 'active' : ''}`}
                      aria-pressed={selected}
                    >
                      {channelIcons[c]()}
                      <span className="social-channel-name">{c}</span>
                      {selected ? <span className="social-channel-check">✓</span> : null}
                      {!connected ? <span className="social-channel-muted">draft</span> : null}
                    </button>
                  )
                })}
              </div>
              <p className="muted social-channel-hint">
                {editingPostId
                  ? 'Editing this post\'s channel directly — create a new post to target other channels.'
                  : 'Creates one draft per selected channel. Live Meta publish is available for Facebook today.'}
              </p>
            </div>

            {/* Facebook Target Page Selection */}
            {wantsFacebook && (
              <div>
                <label className="field-label social-field-label-flat">
                  Target Facebook Page
                  <Select
                    value={selectedPageId || (fbPages[0]?.id ?? '')}
                    onChange={(e) => setSelectedPageId(e.target.value)}
                  >
                    {fbPages.length === 0 ? (
                      <option value="">No connected Facebook pages found</option>
                    ) : (
                      fbPages.map((pg) => (
                        <option key={pg.id} value={pg.id}>
                          {pg.name} (ID: {pg.id})
                        </option>
                      ))
                    )}
                  </Select>
                </label>
                {fbPages.length === 0 && (
                  <div style={{ fontSize: '0.82rem', marginTop: '4px', color: '#dc2626' }}>
                    No connected Facebook Page found. Please connect your Facebook Page in Integrations first.
                  </div>
                )}
              </div>
            )}

            {/* Media Upload & Shoppable Product */}
            <div className="social-grid-2">
              <label className="field-label social-field-label-flat">
                Attach Media Images (you can select more than one)
                <Input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(e) => {
                    onPhotoFiles(e.target.files)
                    e.target.value = ''
                  }}
                  disabled={uploading}
                />
              </label>

              <label className="field-label social-field-label-flat">
                Tag Shoppable Product (Auto-replies price to inbox)
                <Select value={productId} onChange={(e) => setProductId(e.target.value)}>
                  <option value="">None (General brand post)</option>
                  {(products.data ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} — ৳ {p.price}
                    </option>
                  ))}
                </Select>
              </label>
            </div>

            {uploading ? <div className="muted">Uploading photo(s)…</div> : null}
            {photoUrls.length > 0 ? (
              <div className="social-image-preview-box" style={{ flexWrap: 'wrap', display: 'flex', gap: 10 }}>
                {photoUrls.map((url, i) => (
                  <div key={url + i} style={{ position: 'relative' }}>
                    <img
                      src={previewSrcs[i] || resolveMediaUrl(url)}
                      alt={`Preview ${i + 1}`}
                      className="social-image-preview-thumb"
                    />
                    <button
                      type="button"
                      onClick={() => removePhoto(i)}
                      aria-label="Remove photo"
                      style={{
                        position: 'absolute',
                        top: -6,
                        right: -6,
                        width: 22,
                        height: 22,
                        borderRadius: '50%',
                        border: 'none',
                        background: '#dc2626',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: 13,
                        lineHeight: 1,
                      }}
                    >
                      ×
                    </button>
                  </div>
                ))}
                <span className="muted social-image-preview-text">
                  {uploading
                    ? 'Uploading…'
                    : `${photoUrls.length} photo${photoUrls.length > 1 ? 's' : ''} attached and ready to publish.`}
                </span>
              </div>
            ) : null}

            {/* Caption with AI Helper Pills */}
            <div>
              <div className="social-caption-header">
                <label className="field-label social-field-label-flat">
                  Post Caption ({postLanguage})
                </label>
                <div className="social-ai-actions">
                  <button
                    type="button"
                    onClick={() => aiHelp.mutate('caption')}
                    disabled={aiHelp.isPending || uploading}
                    title={uploading ? 'Wait for the photo to finish uploading first' : undefined}
                    className="social-ai-btn"
                  >
                    <Sparkles size={13} />
                    <span>
                      {aiHelp.isPending && aiHelp.variables === 'caption'
                        ? photoUrls.length > 0
                          ? 'Analyzing photo…'
                          : 'Writing…'
                        : locale === 'bn'
                          ? 'AI ক্যাপশন'
                          : 'AI Caption'}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => aiHelp.mutate('hashtags')}
                    disabled={aiHelp.isPending || uploading}
                    title={uploading ? 'Wait for the photo to finish uploading first' : undefined}
                    className="social-ai-btn"
                  >
                    <Hash size={13} />
                    <span>
                      {aiHelp.isPending && aiHelp.variables === 'hashtags'
                        ? photoUrls.length > 0
                          ? 'Analyzing photo…'
                          : 'Writing…'
                        : locale === 'bn'
                          ? 'হ্যাশট্যাগ'
                          : 'Viral Hashtags'}
                    </span>
                  </button>
                </div>
              </div>
              <Textarea
                rows={4}
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder={
                  locale === 'bn'
                    ? 'পোস্টের ক্যাপশন লিখুন অথবা AI ক্যাপশন চাপুন…'
                    : 'Write your product announcement or click AI Caption…'
                }
                required
              />
              <p className="muted social-channel-hint">
                {locale === 'bn'
                  ? 'ভাষা সেটিংস: বাংলা — AI ক্যাপশন বাংলায় তৈরি হবে। ইংরেজির জন্য উপরের Language পরিবর্তন করুন।'
                  : 'Language setting: English — AI captions will be in English. Switch Language in the header for Bangla.'}
              </p>
            </div>

            {/* Hashtags and First Comment */}
            <div className="social-grid-2">
              <label className="field-label social-field-label-flat">
                Hashtags (Space separated)
                <Input
                  value={hashtags}
                  onChange={(e) => setHashtags(e.target.value)}
                  placeholder="fashion bd retail newarrival"
                />
              </label>

              <label className="field-label social-field-label-flat">
                First Comment (Auto-pinned)
                <Input
                  value={firstComment}
                  onChange={(e) => setFirstComment(e.target.value)}
                  placeholder="Drop a comment or DM for order link!"
                />
              </label>
            </div>

            <div className="social-form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  resetComposer()
                  setShowComposer(false)
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={create.isPending || uploading || channels.length === 0}>
                <Send size={15} />
                <span>
                  {create.isPending
                    ? editingPostId
                      ? 'Saving changes…'
                      : 'Saving drafts…'
                    : editingPostId
                      ? 'Save Changes'
                      : `Save to ${channels.length} channel${channels.length > 1 ? 's' : ''}`}
                </span>
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Posts Grid matching exact Active Channels style */}
      <div className="channels-section-container">
        <div className="channels-header-bar">
          <div className="channels-title-row">
            <span className="channels-title-icon">
              <LayoutGrid size={20} strokeWidth={2.4} />
            </span>
            <h2 className="channels-heading-text">POST FEED & BROADCASTS</h2>
          </div>
          <div className="live-sync-pill">
            <span className="live-sync-dot" />
            <span>Feed Sync Active</span>
          </div>
        </div>

        {posts.isLoading ? (
          <Loading />
        ) : posts.isError ? (
          <ErrorBox error={posts.error} />
        ) : !postList.length ? (
          <EmptyState
            title="No social posts published yet"
            hint="Click 'Create New Post' above to draft and broadcast shoppable product posts."
          />
        ) : (
          <div className="active-channels-grid">
            {postList.map((p) => {
              const ch = (p.channel || 'facebook').toLowerCase()
              const iconFn = channelIcons[ch] || channelIcons.facebook
              const isPublished = p.status === 'published'
              const isFailed = p.status === 'failed'

              return (
                <div key={p.id} className="channel-card-modern">
                  <div>
                    {/* Header */}
                    <div className="channel-top-row">
                      <div className="channel-brand-group">
                        <div className="channel-brand-icon-wrap social-brand-icon-sm">
                          {iconFn()}
                        </div>
                        <div className="channel-brand-info">
                          <h3 className="social-channel-name">
                            {p.page_name ? p.page_name : `${p.channel} Broadcast`}
                          </h3>
                          <p className="channel-brand-sub">
                            {p.page_name ? `${p.channel} Page • Ref: #${shortId(p.id)}` : `Ref: #${shortId(p.id)}`}
                          </p>
                        </div>
                      </div>

                      {isPublished ? (
                        <div className="channel-status-pill-active channel-status-pill-emerald">
                          <span className="channel-status-active-dot emerald" />
                          <span>Published</span>
                        </div>
                      ) : isFailed ? (
                        <div className="channel-status-pill-active channel-status-pill-rose">
                          <span className="channel-status-active-dot rose" />
                          <span>Failed (Meta API)</span>
                        </div>
                      ) : (
                        <div className="channel-status-pill-active channel-status-pill-amber">
                          <span className="channel-status-active-dot amber" />
                          <span>{p.status === 'scheduled' ? 'Scheduled Queue' : 'Draft Queue'}</span>
                        </div>
                      )}
                    </div>

                    {/* Image Thumbnail(s) & Caption */}
                    {p.photo_urls?.length ? (
                      <div className="social-post-thumb-row">
                        {p.photo_urls.slice(0, 3).map((url, i) => (
                          <div key={url + i} className="social-post-thumb-wrap">
                            <img
                              src={resolveMediaUrl(url)}
                              alt={`Post media ${i + 1}`}
                              className="social-post-thumb"
                            />
                            {i === 2 && p.photo_urls.length > 3 ? (
                              <div className="social-post-thumb-more">+{p.photo_urls.length - 3}</div>
                            ) : null}
                          </div>
                        ))}
                        {p.photo_urls.length > 1 ? (
                          <span className="muted social-post-thumb-count">
                            {p.photo_urls.length} photos
                          </span>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="social-post-body-wrap">
                      <p className="social-post-body-text">
                        {p.caption || 'No caption provided.'}
                      </p>
                    </div>

                    {/* Bullet features & Product tag */}
                    <div className="channel-features-list">
                      {p.tagged_product_id ? (
                        <div className="channel-feature-bullet">
                          <Tag size={16} color="#2563eb" />
                          <span>Shoppable Product Linked &bull; Auto-replies in DMs</span>
                        </div>
                      ) : null}

                      {p.first_comment ? (
                        <div className="channel-feature-bullet">
                          <MessageCircle size={16} color="#2563eb" />
                          <span>Pinned Comment: "{p.first_comment}"</span>
                        </div>
                      ) : null}

                      {p.hashtags?.length ? (
                        <div className="channel-feature-bullet">
                          <Hash size={16} color="#2563eb" />
                          <span>{p.hashtags.map((h) => `#${h}`).join(' ')}</span>
                        </div>
                      ) : null}
                    </div>
                  </div>

                  {/* Bottom Action Block */}
                  <div className="channel-account-block">
                    {isPublished ? (
                      <>
                        <button type="button" disabled className="channel-btn-limit-reached">
                          Live on {p.page_name || 'Social Grid'}
                        </button>
                        <p className="channel-limit-caption">
                          Broadcast live. Incoming comments are synced to your Inbox automatically.
                        </p>
                      </>
                    ) : isFailed ? (
                      <>
                        <button
                          type="button"
                          className="channel-connect-button"
                          onClick={() => publish.mutate(p.id)}
                          disabled={publish.isPending}
                        >
                          <Send size={16} />
                          <span>Retry Publish</span>
                        </button>
                        <p className="channel-limit-caption" style={{ color: '#dc2626', fontWeight: 500 }}>
                          {p.error_message || 'Meta rejected the request: Missing pages_manage_posts or pages_read_engagement permissions.'}
                        </p>
                        <p className="channel-limit-caption" style={{ color: '#64748b', fontSize: '0.78rem' }}>
                          How to fix: In Integrations, click Reconnect Facebook (we updated the OAuth permissions to request post management). If generating tokens manually in Meta Graph API Explorer, ensure you generate a Page Access Token with pages_manage_posts and pages_read_engagement.
                        </p>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="channel-connect-button"
                        onClick={() => publish.mutate(p.id)}
                        disabled={publish.isPending}
                      >
                        <Send size={16} />
                        <span>Publish to {p.page_name || p.channel} Now</span>
                      </button>
                    )}

                    <div className="social-post-manage-row" style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                      {!isPublished ? (
                        <button
                          type="button"
                          className="channel-connect-button"
                          style={{ flex: 1 }}
                          onClick={() => startEdit(p)}
                        >
                          <Pencil size={14} />
                          <span>Edit</span>
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="channel-connect-button"
                        style={{ flex: 1, color: '#dc2626' }}
                        onClick={() => {
                          if (window.confirm('Delete this post? This cannot be undone.')) {
                            remove.mutate(p.id)
                          }
                        }}
                        disabled={remove.isPending}
                      >
                        <Trash2 size={14} />
                        <span>Delete</span>
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
