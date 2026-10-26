import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Eye, Plus, Upload } from 'lucide-react'
import { api } from '../api/endpoints'
import { money } from '../lib/format'
import { parseProductCsv } from '../lib/csv'
import { resolveMediaUrl } from '../lib/media'
import { useAuth } from '../auth/AuthContext'
import { roleAtLeast } from '../lib/roles'
import { useLocale } from '../i18n/LocaleContext'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { Modal } from '../components/ui/Modal'
import { useToast } from '../components/ui/ToastProvider'
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
  Table,
  Textarea,
} from '../components/ui/primitives'
import type { Product } from '../types/api'

// Facebook CDN URLs are proxied through the backend by resolveMediaUrl,
// so ProductPhoto just renders a normal <img> for all sources.
function ProductPhoto({
  url,
  name,
  size = 36,
  style: extraStyle,
}: {
  url: string | null | undefined
  name: string
  size?: number
  style?: React.CSSProperties
}) {
  const resolved = resolveMediaUrl(url)

  if (!resolved) {
    return (
      <div
        style={{
          width: size,
          height: size,
          borderRadius: size < 80 ? 8 : 10,
          background: '#f1f5f9',
          flexShrink: 0,
          ...extraStyle,
        }}
      />
    )
  }

  return (
    <img
      src={resolved}
      alt={name}
      style={{
        width: size,
        height: size,
        borderRadius: size < 80 ? 8 : 10,
        objectFit: 'cover',
        flexShrink: 0,
        ...extraStyle,
      }}
      onError={(e) => {
        const img = e.currentTarget
        img.style.display = 'none'
      }}
    />
  )
}

export function ProductsPage() {
  const { t } = useLocale()
  const qc = useQueryClient()
  const { role } = useAuth()
  const { showToast } = useToast()
  const canCreate = roleAtLeast(role, 'sales')
  const canDelete = roleAtLeast(role, 'admin')
  const [q, setQ] = useState('')

  // Create form state
  const [name, setName] = useState('')
  const [price, setPrice] = useState('')
  const [category, setCategory] = useState('')
  const [description, setDescription] = useState('')
  const [photoUrl, setPhotoUrl] = useState('')
  const [postLink, setPostLink] = useState('')
  const [sku, setSku] = useState('')
  const [stock, setStock] = useState('10')
  const [pageId, setPageId] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)

  // Bulk import state
  const [csv, setCsv] = useState('T-Shirt,499,apparel,10\nMug,299,home,25')
  const [showImportModal, setShowImportModal] = useState(false)
  const [csvFileName, setCsvFileName] = useState('')

  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  // Preview state
  const [previewProduct, setPreviewProduct] = useState<Product | null>(null)

  // Edit form state
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [editName, setEditName] = useState('')
  const [editPrice, setEditPrice] = useState('')
  const [editCategory, setEditCategory] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editPhotoUrl, setEditPhotoUrl] = useState('')
  const [editPostLink, setEditPostLink] = useState('')
  const [editSku, setEditSku] = useState('')
  const [editPageId, setEditPageId] = useState('')
  const [editStockDelta, setEditStockDelta] = useState('0')

  const shop = useQuery({ queryKey: ['shop'], queryFn: api.shop.me })
  const products = useQuery({
    queryKey: ['products', 'product', q],
    queryFn: () => api.products.list(q || undefined, 'product'),
  })
  const pages = useQuery({ queryKey: ['page-ai-profiles'], queryFn: () => api.pageAi.list() })
  const pageNameById = new Map((pages.data ?? []).map((p) => [p.page_id, `${p.page_name} (${p.platform})`]))

  function resetAddForm() {
    setName('')
    setPrice('')
    setCategory('')
    setDescription('')
    setPhotoUrl('')
    setPostLink('')
    setSku('')
    setStock('10')
    setPageId('')
  }

  const create = useMutation({
    mutationFn: () =>
      api.products.create({
        name,
        price: Number(price),
        kind: 'product',
        category: category || undefined,
        description: description || undefined,
        photo_url: photoUrl || undefined,
        post_link: postLink || undefined,
        page_id: pageId || undefined,
        variants: [{ sku: sku || undefined, attributes: { size: 'default' }, stock_qty: Number(stock) || 0, reorder_point: 2 }],
      }),
    onSuccess: () => {
      resetAddForm()
      setShowAddModal(false)
      showToast('Product added.', 'success')
      qc.invalidateQueries({ queryKey: ['products'] })
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not add product.', 'error')
    },
  })

  const update = useMutation({
    mutationFn: async () => {
      if (!editingProduct) return
      await api.products.update(editingProduct.id, {
        name: editName,
        price: Number(editPrice),
        category: editCategory || null,
        description: editDescription || null,
        photo_url: editPhotoUrl || null,
        post_link: editPostLink || null,
        page_id: editPageId || null,
        sku: editSku || null,
      })
      // Adjust stock on the default variant if the user changed it
      const delta = Number(editStockDelta)
      if (delta !== 0 && editingProduct.variants.length > 0) {
        await api.products.adjustStock({
          variant_id: editingProduct.variants[0].id,
          delta_qty: delta,
          reason: 'stock_count',
          note: 'Manual adjustment from product edit',
        })
      }
    },
    onSuccess: () => {
      setEditingProduct(null)
      showToast('Product updated.', 'success')
      qc.invalidateQueries({ queryKey: ['products'] })
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not update product.', 'error')
    },
  })

  const bulkImport = useMutation({
    mutationFn: () => api.products.importBulk(parseProductCsv(csv)),
    onSuccess: (data) => {
      showToast(`Imported ${data.created} product${data.created === 1 ? '' : 's'}.`, 'success')
      setShowImportModal(false)
      qc.invalidateQueries({ queryKey: ['products'] })
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'CSV import failed.', 'error')
    },
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.products.remove(id),
    onSuccess: () => {
      setDeleteId(null)
      showToast('Product deleted.', 'success')
      qc.invalidateQueries({ queryKey: ['products'] })
    },
    onError: (err: unknown) => {
      showToast(err instanceof Error ? err.message : 'Could not delete product.', 'error')
    },
  })

  const currency = shop.data?.currency ?? 'BDT'

  async function onPhotoFile(file: File | null, isEdit = false) {
    if (!file) return
    setUploading(true)
    try {
      const res = await api.media.upload(file)
      if (isEdit) {
        setEditPhotoUrl(res.url)
      } else {
        setPhotoUrl(res.url)
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Photo upload failed.', 'error')
    } finally {
      setUploading(false)
    }
  }

  function onCsvFile(file: File | null) {
    if (!file) return
    setCsvFileName(file.name)
    const reader = new FileReader()
    reader.onload = () => {
      const text = typeof reader.result === 'string' ? reader.result : ''
      setCsv(text)
      const parsed = parseProductCsv(text)
      showToast(`Loaded ${parsed.length} row${parsed.length === 1 ? '' : 's'} from ${file.name}. Review and click Import.`, 'success')
    }
    reader.onerror = () => {
      showToast('Could not read that CSV file.', 'error')
    }
    reader.readAsText(file)
  }

  function handleStartEdit(p: Product) {
    setEditingProduct(p)
    setEditName(p.name)
    setEditPrice(String(p.price))
    setEditCategory(p.category || '')
    setEditDescription(p.description || '')
    setEditPhotoUrl(p.photo_url || '')
    setEditPostLink(p.post_link || '')
    setEditSku(p.variants[0]?.sku || '')
    setEditPageId(p.page_id || '')
    setEditStockDelta('0')
  }

  function handleCancelEdit() {
    setEditingProduct(null)
  }

  return (
    <>
      <PageHeader
        title={t('products')}
        subtitle="Physical catalogue with photo, variants, stock alerts, and bulk CSV import (FR-CAT)."
        actions={
          canCreate ? (
            <div className="row" style={{ gap: '0.5rem' }}>
              <Button variant="secondary" onClick={() => setShowImportModal(true)}>
                <Upload size={15} style={{ marginRight: 6 }} />
                Bulk Import (CSV)
              </Button>
              <Button onClick={() => setShowAddModal(true)}>
                <Plus size={15} style={{ marginRight: 6 }} />
                Add Product
              </Button>
            </div>
          ) : undefined
        }
      />

      <div className="row">
        <Input
          placeholder="Search products…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ maxWidth: 280 }}
        />
      </div>

      <Panel title="Catalogue">
        {products.isLoading ? (
          <Loading />
        ) : products.isError ? (
          <ErrorBox error={products.error} />
        ) : !products.data?.length ? (
          <EmptyState title="No products" hint="Add a product or bulk import a CSV." />
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Category</th>
                <th>Page</th>
                <th>Price</th>
                <th>Stock</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {products.data.map((p) => {
                const qty = p.variants.reduce((s, v) => s + v.stock_qty, 0)
                const low = p.variants.some((v) => v.stock_qty <= v.reorder_point)

                return (
                  <tr key={p.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                        <ProductPhoto url={p.photo_url} name={p.name} size={36} />
                        <div>
                          <strong>{p.name}</strong>
                          {p.description ? <div className="muted">{p.description.slice(0, 60)}</div> : null}
                        </div>
                      </div>
                    </td>
                    <td>{p.category || '—'}</td>
                    <td>
                      {p.page_id ? (
                        <Badge tone="info">{pageNameById.get(p.page_id) ?? p.page_id}</Badge>
                      ) : (
                        <span className="muted">All pages</span>
                      )}
                    </td>
                    <td>{money(p.price, currency)}</td>
                    <td>
                      {qty}{' '}
                      {low ? <Badge tone="warn">low</Badge> : null}
                      {qty <= 0 ? <Badge tone="danger">sold out</Badge> : null}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                        <Button size="sm" variant="secondary" onClick={() => setPreviewProduct(p)}>
                          <Eye size={14} style={{ marginRight: 4 }} />
                          Preview
                        </Button>
                        {canCreate ? (
                          <Button size="sm" variant="secondary" onClick={() => handleStartEdit(p)}>
                            Edit
                          </Button>
                        ) : null}
                        {canDelete ? (
                          <Button size="sm" variant="danger" onClick={() => setDeleteId(p.id)}>
                            Delete
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </Table>
        )}
      </Panel>

      <Modal
        open={Boolean(previewProduct)}
        title={previewProduct?.name ?? 'Product preview'}
        onClose={() => setPreviewProduct(null)}
        width={480}
      >
        {previewProduct ? (
          <div className="stack">
            {previewProduct.photo_url ? (
              <img
                src={resolveMediaUrl(previewProduct.photo_url)}
                alt={previewProduct.name}
                style={{ width: '100%', maxHeight: 320, objectFit: 'cover', borderRadius: 10 }}
                onError={(e) => { e.currentTarget.style.display = 'none' }}
              />
            ) : (
              <div
                style={{
                  width: '100%',
                  height: 180,
                  borderRadius: 10,
                  background: '#f1f5f9',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#94a3b8',
                  fontSize: 13,
                }}
              >
                No photo
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#0f172a' }}>
                {money(previewProduct.price, currency)}
              </div>
              {previewProduct.category ? <Badge tone="neutral">{previewProduct.category}</Badge> : null}
            </div>

            <div>
              {previewProduct.page_id ? (
                <Badge tone="info">{pageNameById.get(previewProduct.page_id) ?? previewProduct.page_id}</Badge>
              ) : (
                <Badge tone="neutral">Shared across all pages</Badge>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {(() => {
                const qty = previewProduct.variants.reduce((s, v) => s + v.stock_qty, 0)
                const low = previewProduct.variants.some((v) => v.stock_qty <= v.reorder_point)
                return (
                  <>
                    <Badge tone={qty <= 0 ? 'danger' : low ? 'warn' : 'good'}>{qty} in stock</Badge>
                    {previewProduct.pricing_mode ? <Badge tone="neutral">{previewProduct.pricing_mode}</Badge> : null}
                  </>
                )
              })()}
            </div>

            {previewProduct.description ? (
              <p style={{ margin: 0, color: '#475569', fontSize: 14, lineHeight: 1.5 }}>
                {previewProduct.description}
              </p>
            ) : (
              <p className="muted" style={{ margin: 0 }}>
                No description provided.
              </p>
            )}

            {previewProduct.post_link ? (
              <a
                href={previewProduct.post_link}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 13, color: '#3b82f6', fontWeight: 500 }}
              >
                View Facebook post ↗
              </a>
            ) : null}

            {canCreate ? (
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                <Button
                  variant="secondary"
                  onClick={() => {
                    handleStartEdit(previewProduct)
                    setPreviewProduct(null)
                  }}
                >
                  Edit
                </Button>
                <Button variant="secondary" onClick={() => setPreviewProduct(null)}>
                  Close
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </Modal>

      <Modal open={showAddModal} title="Add product" onClose={() => setShowAddModal(false)}>
        <div className="stack">
          <label className="field-label">
            Name
            <Input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label className="field-label">
            Price
            <Input type="number" value={price} onChange={(e) => setPrice(e.target.value)} />
          </label>
          <label className="field-label">
            Product code / SKU (e.g. UT1001 — customers can order by this code in chat)
            <Input value={sku} onChange={(e) => setSku(e.target.value)} placeholder="e.g. UT1001" />
          </label>
          <label className="field-label">
            Category
            <Input value={category} onChange={(e) => setCategory(e.target.value)} />
          </label>
          <label className="field-label">
            Page (which connected page sells this — leave blank to share across all pages)
            <Select value={pageId} onChange={(e) => setPageId(e.target.value)}>
              <option value="">Shared across all pages</option>
              {(pages.data ?? []).map((p) => (
                <option key={p.page_id} value={p.page_id}>
                  {p.page_name} ({p.platform})
                </option>
              ))}
            </Select>
          </label>
          <label className="field-label">
            Initial stock
            <Input type="number" value={stock} onChange={(e) => setStock(e.target.value)} />
          </label>
          <label className="field-label">
            Photo URL
            <Input value={photoUrl} onChange={(e) => setPhotoUrl(e.target.value)} />
          </label>
          <label className="field-label">
            Facebook Post Link
            <Input value={postLink} onChange={(e) => setPostLink(e.target.value)} />
          </label>
          <label className="field-label">
            Upload photo
            <Input type="file" accept="image/*" onChange={(e) => onPhotoFile(e.target.files?.[0] ?? null)} />
          </label>
          {uploading ? <div className="muted">Uploading…</div> : null}
          <label className="field-label">
            Description
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          {create.isError ? <ErrorBox error={create.error} /> : null}
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
            <Button onClick={() => create.mutate()} disabled={!name || !price || create.isPending}>
              {create.isPending ? 'Adding…' : 'Add Product'}
            </Button>
            <Button variant="secondary" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(editingProduct)}
        title={`Edit product: ${editingProduct?.name ?? ''}`}
        onClose={handleCancelEdit}
      >
        <div className="stack">
          <label className="field-label">
            Name
            <Input value={editName} onChange={(e) => setEditName(e.target.value)} required />
          </label>
          <label className="field-label">
            Price
            <Input type="number" value={editPrice} onChange={(e) => setEditPrice(e.target.value)} />
          </label>
          <label className="field-label">
            Product code / SKU (e.g. UT1001)
            <Input value={editSku} onChange={(e) => setEditSku(e.target.value)} placeholder="e.g. UT1001" />
          </label>
          <label className="field-label">
            Category
            <Input value={editCategory} onChange={(e) => setEditCategory(e.target.value)} />
          </label>
          <label className="field-label">
            Page (which connected page sells this — leave blank to share across all pages)
            <Select value={editPageId} onChange={(e) => setEditPageId(e.target.value)}>
              <option value="">Shared across all pages</option>
              {(pages.data ?? []).map((p) => (
                <option key={p.page_id} value={p.page_id}>
                  {p.page_name} ({p.platform})
                </option>
              ))}
            </Select>
          </label>
          <label className="field-label">
            Photo URL
            <Input value={editPhotoUrl} onChange={(e) => setEditPhotoUrl(e.target.value)} />
          </label>
          <label className="field-label">
            Facebook Post Link
            <Input value={editPostLink} onChange={(e) => setEditPostLink(e.target.value)} />
          </label>
          <label className="field-label">
            Upload new photo
            <Input type="file" accept="image/*" onChange={(e) => onPhotoFile(e.target.files?.[0] ?? null, true)} />
          </label>
          {uploading ? <div className="muted">Uploading…</div> : null}
          <label className="field-label">
            Description
            <Textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} />
          </label>
          {(() => {
            const currentStock = editingProduct?.variants.reduce((s, v) => s + v.stock_qty, 0) ?? 0
            const delta = Number(editStockDelta) || 0
            const newStock = currentStock + delta
            return (
              <label className="field-label">
                Adjust stock (+ to add, − to remove)
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Input
                    type="number"
                    value={editStockDelta}
                    onChange={(e) => setEditStockDelta(e.target.value)}
                    style={{ width: 100 }}
                  />
                  <span className="muted" style={{ fontSize: 13 }}>
                    Current: {currentStock} → New: {newStock < 0 ? 0 : newStock}
                  </span>
                </div>
              </label>
            )
          })()}
          {update.isError ? <ErrorBox error={update.error} /> : null}
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
            <Button onClick={() => update.mutate()} disabled={!editName || !editPrice || update.isPending}>
              {update.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
            <Button variant="secondary" onClick={handleCancelEdit}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={showImportModal} title="Bulk import (CSV)" onClose={() => setShowImportModal(false)} width={560}>
        <div className="stack">
          <label className="field-label">
            Upload a CSV file
            <Input type="file" accept=".csv,text/csv" onChange={(e) => onCsvFile(e.target.files?.[0] ?? null)} />
          </label>
          {csvFileName ? <div className="muted">Loaded: {csvFileName}</div> : null}
          <p className="muted">
            Each row: name, price, category, stock_qty — a header row and quoted fields (e.g. names containing
            commas) are handled automatically. You can also paste/edit rows directly below.
          </p>
          <Textarea value={csv} onChange={(e) => setCsv(e.target.value)} rows={8} />
          {bulkImport.isError ? <ErrorBox error={bulkImport.error} /> : null}
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
            <Button onClick={() => bulkImport.mutate()} disabled={!csv.trim() || bulkImport.isPending}>
              {bulkImport.isPending ? 'Importing…' : 'Import'}
            </Button>
            <Button variant="secondary" onClick={() => setShowImportModal(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteId)}
        title="Delete product?"
        message="This removes the catalogue item and its variants. Order history remains."
        danger
        confirmLabel="Delete"
        onConfirm={() => (deleteId ? remove.mutate(deleteId) : undefined)}
        onCancel={() => setDeleteId(null)}
      />
    </>
  )
}
