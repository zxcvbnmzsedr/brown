import { ChevronDown, ChevronRight, FolderTree, Layers3, Pencil, Plus, Save, Trash2, WalletCards, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../../api/client'
import type { Asset, AssetGroup, AssetPayload, BucketPayload, GroupPayload, PortfolioBucket } from '../../types'
import { formatMoney, formatPercent } from '../../utils/format'
import { AssetCreateForm } from './AssetCreateForm'
import { emptyBucketForm, emptyGroupForm } from './constants'
import type { BucketFormState, GroupFormState } from './constants'

type EditorTarget =
  | { type: 'create-bucket' }
  | { type: 'edit-bucket'; id: number }
  | { type: 'create-group'; bucketId: number }
  | { type: 'edit-group'; id: number }
  | null

type AssetCreateTarget =
  | { type: 'group'; groupId: number; label: string }
  | { type: 'unassigned'; label: string }

interface StructureTabProps {
  structure: PortfolioBucket[]
  assets: Asset[]
  onAssetChange: (asset: Asset, overrides: Partial<AssetPayload>) => Promise<void>
  onAssetDelete: (asset: Asset) => Promise<void>
  onRefresh: () => Promise<void>
  onMutate: (task: () => Promise<unknown>) => Promise<void>
}

export function StructureTab({ structure, assets, onAssetChange, onAssetDelete, onRefresh, onMutate }: StructureTabProps) {
  const [editor, setEditor] = useState<EditorTarget>(null)
  const [bucketForm, setBucketForm] = useState<BucketFormState>(emptyBucketForm)
  const [groupForm, setGroupForm] = useState<GroupFormState>(emptyGroupForm)
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({})
  const [unassignedCollapsed, setUnassignedCollapsed] = useState(false)
  const [assetCreateTarget, setAssetCreateTarget] = useState<AssetCreateTarget | null>(null)
  const groupOptions = useMemo(
    () => structure.flatMap((bucket) => bucket.groups.map((group) => ({ bucket, group }))),
    [structure],
  )
  const assetsByGroup = useMemo(() => {
    const grouped = new Map<number, Asset[]>()
    for (const asset of assets) {
      if (!asset.group_id || !asset.include_in_portfolio) continue
      const current = grouped.get(asset.group_id) ?? []
      current.push(asset)
      grouped.set(asset.group_id, current)
    }
    return grouped
  }, [assets])
  const unassignedAssets = useMemo(
    () => assets.filter((asset) => !asset.include_in_portfolio || !asset.group_id),
    [assets],
  )

  function closeEditor() {
    setEditor(null)
    setAssetCreateTarget(null)
    setBucketForm(emptyBucketForm)
    setGroupForm(emptyGroupForm)
  }

  function openCreateBucket() {
    setBucketForm(emptyBucketForm)
    setAssetCreateTarget(null)
    setEditor({ type: 'create-bucket' })
  }

  function openEditBucket(bucket: PortfolioBucket) {
    setBucketForm({
      name: bucket.name,
      targetWeight: String(bucket.target_weight * 100),
      displayOrder: String(bucket.display_order),
    })
    setAssetCreateTarget(null)
    setEditor({ type: 'edit-bucket', id: bucket.id })
  }

  function openCreateGroup(bucketId: number) {
    setGroupForm({ ...emptyGroupForm, bucketId: String(bucketId) })
    setAssetCreateTarget(null)
    setEditor({ type: 'create-group', bucketId })
    setCollapsed((prev) => ({ ...prev, [bucketId]: false }))
  }

  function openEditGroup(group: AssetGroup) {
    setGroupForm({
      bucketId: String(group.bucket_id),
      name: group.name,
      targetWeight: String(group.target_weight * 100),
      displayOrder: String(group.display_order),
    })
    setAssetCreateTarget(null)
    setEditor({ type: 'edit-group', id: group.id })
  }

  async function submitBucket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const payload: BucketPayload = {
      name: bucketForm.name.trim(),
      target_weight: Number(bucketForm.targetWeight) / 100,
      display_order: Number(bucketForm.displayOrder || 0),
    }
    await onMutate(() =>
      editor?.type === 'edit-bucket'
        ? api.updateBucket(editor.id, payload)
        : api.createBucket(payload),
    )
    closeEditor()
  }

  async function submitGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const payload: GroupPayload = {
      bucket_id: Number(groupForm.bucketId),
      name: groupForm.name.trim(),
      target_weight: Number(groupForm.targetWeight) / 100,
      display_order: Number(groupForm.displayOrder || 0),
    }
    await onMutate(() =>
      editor?.type === 'edit-group'
        ? api.updateGroup(editor.id, payload)
        : api.createGroup(payload),
    )
    closeEditor()
  }

  return (
    <div className="structure-tab">
      <div className="structure-tab-header">
        <div>
          <h2>组合结构</h2>
          <p>资产大类、细则和标的在同一棵树里维护。</p>
        </div>
        {editor?.type !== 'create-bucket' && (
          <button className="primary-button" type="button" onClick={openCreateBucket}>
            <Plus size={16} />
            新增大类
          </button>
        )}
      </div>

      <div className="structure-tree">
        {editor?.type === 'create-bucket' && (
          <div className="bucket-card-v2 bucket-card-v2-editing">
            <BucketDirectForm
              form={bucketForm}
              onChange={setBucketForm}
              onCancel={closeEditor}
              onSubmit={submitBucket}
              mode="create"
            />
          </div>
        )}

        {structure.length === 0 && editor?.type !== 'create-bucket' && (
          <div className="empty-state">
            <p>还没有资产大类，点上面的“新增大类”创建一个吧。</p>
          </div>
        )}

        {structure.map((bucket) => {
          const isCollapsed = collapsed[bucket.id] ?? false
          const groupTotal = bucket.groups.reduce((sum, g) => sum + g.target_weight, 0)
          const editingThisBucket = editor?.type === 'edit-bucket' && editor.id === bucket.id
          const creatingGroupHere = editor?.type === 'create-group' && editor.bucketId === bucket.id
          return (
            <div className="bucket-card-v2" key={bucket.id}>
              {editingThisBucket ? (
                <BucketDirectForm
                  form={bucketForm}
                  onChange={setBucketForm}
                  onCancel={closeEditor}
                  onSubmit={submitBucket}
                  mode="edit"
                />
              ) : (
                <header className="bucket-card-v2-header">
                  <button
                    className="icon-button bucket-toggle"
                    type="button"
                    aria-label={isCollapsed ? '展开' : '折叠'}
                    onClick={() =>
                      setCollapsed((prev) => ({ ...prev, [bucket.id]: !isCollapsed }))
                    }
                  >
                    {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                  </button>
                  <div className="bucket-card-v2-title">
                    <div className="bucket-eye">
                      <Layers3 size={15} />
                    </div>
                    <div>
                      <span className="structure-eyebrow">资产大类</span>
                      <strong>{bucket.name}</strong>
                    </div>
                  </div>
                  <div className="bucket-card-v2-stats">
                    <span className="bucket-target-pill">目标 {formatPercent(bucket.target_weight)}</span>
                    <span className="bucket-actual-pill">细则合计 {formatPercent(groupTotal)}</span>
                    <div className="bucket-actions-row">
                      <button
                        className="icon-button"
                        type="button"
                        aria-label={`编辑 ${bucket.name}`}
                        onClick={() => openEditBucket(bucket)}
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        className="icon-button danger-button"
                        type="button"
                        aria-label={`删除 ${bucket.name}`}
                        onClick={() => void onMutate(() => api.deleteBucket(bucket.id))}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                </header>
              )}

              {!isCollapsed && (
                <div className="group-rows">
                  {bucket.groups.length === 0 && !creatingGroupHere && (
                    <div className="empty-inline">还没有细则，点右下角“新增细则”。</div>
                  )}

                  {bucket.groups.map((group) => {
                    const editingThisGroup = editor?.type === 'edit-group' && editor.id === group.id
                    const groupAssets = assetsByGroup.get(group.id) ?? []
                    const creatingAssetHere =
                      assetCreateTarget?.type === 'group' && assetCreateTarget.groupId === group.id
                    return (
                      <div className="group-branch-v2" key={group.id}>
                        {editingThisGroup ? (
                          <GroupDirectForm
                            form={groupForm}
                            structure={structure}
                            onChange={setGroupForm}
                            onCancel={closeEditor}
                            onSubmit={submitGroup}
                            mode="edit"
                          />
                        ) : (
                          <div className="group-row-v2">
                            <button
                              type="button"
                              className="group-name"
                              onClick={() => openEditGroup(group)}
                            >
                              <FolderTree size={15} />
                              <span>{group.name}</span>
                              <strong className="group-target">{formatPercent(group.target_weight)}</strong>
                            </button>
                            <div className="group-row-v2-actions">
                              <span className="bucket-actual-pill">{groupAssets.length} 个标的</span>
                              <button
                                className="icon-button"
                                type="button"
                                aria-label={`编辑 ${group.name}`}
                                onClick={() => openEditGroup(group)}
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                className="icon-button danger-button"
                                type="button"
                                aria-label={`删除 ${group.name}`}
                                onClick={() => void onMutate(() => api.deleteGroup(group.id))}
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>
                        )}
                        <AssetRows
                          assets={groupAssets}
                          groupOptions={groupOptions}
                          onAssetChange={onAssetChange}
                          onAssetDelete={onAssetDelete}
                        />
                        {creatingAssetHere ? (
                          <AssetCreateForm
                            target={{
                              groupId: group.id,
                              includeInPortfolio: true,
                              label: assetCreateTarget.label,
                            }}
                            assets={assets}
                            onSaved={onRefresh}
                            onCancel={() => setAssetCreateTarget(null)}
                          />
                        ) : (
                          <button
                            className="add-row-button asset-add-row-button"
                            type="button"
                            onClick={() => {
                              setEditor(null)
                              setAssetCreateTarget({
                                type: 'group',
                                groupId: group.id,
                                label: `${bucket.name} / ${group.name}`,
                              })
                            }}
                          >
                            <Plus size={14} />
                            新增标的
                          </button>
                        )}
                      </div>
                    )
                  })}

                  {creatingGroupHere && (
                    <GroupDirectForm
                      form={groupForm}
                      structure={structure}
                      onChange={setGroupForm}
                      onCancel={closeEditor}
                      onSubmit={submitGroup}
                      mode="create"
                    />
                  )}

                  {!creatingGroupHere && (
                    <button
                      className="add-row-button"
                      type="button"
                      onClick={() => openCreateGroup(bucket.id)}
                    >
                      <Plus size={14} />
                      新增细则
                    </button>
                  )}
                </div>
              )}
            </div>
          )
        })}

        <div className="bucket-card-v2">
          <header className="bucket-card-v2-header">
            <button
              className="icon-button bucket-toggle"
              type="button"
              aria-label={unassignedCollapsed ? '展开未纳入组合标的' : '折叠未纳入组合标的'}
              onClick={() => setUnassignedCollapsed((current) => !current)}
            >
              {unassignedCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
            </button>
            <div className="bucket-card-v2-title">
              <div className="bucket-eye">
                <WalletCards size={15} />
              </div>
              <div>
                <span className="structure-eyebrow">标的暂存区</span>
                <strong>未纳入组合</strong>
              </div>
            </div>
            <div className="bucket-card-v2-stats">
              <span className="bucket-actual-pill">{unassignedAssets.length} 个标的</span>
            </div>
          </header>
          {!unassignedCollapsed && (
            <div className="group-rows">
              <AssetRows
                assets={unassignedAssets}
                groupOptions={groupOptions}
                onAssetChange={onAssetChange}
                onAssetDelete={onAssetDelete}
                emptyText="没有未纳入组合的标的。"
              />
              {assetCreateTarget?.type === 'unassigned' ? (
                <AssetCreateForm
                  target={{
                    groupId: null,
                    includeInPortfolio: false,
                    label: assetCreateTarget.label,
                  }}
                  assets={assets}
                  onSaved={onRefresh}
                  onCancel={() => setAssetCreateTarget(null)}
                />
              ) : (
                <button
                  className="add-row-button asset-add-row-button"
                  type="button"
                  onClick={() => {
                    setEditor(null)
                    setAssetCreateTarget({ type: 'unassigned', label: '未纳入组合' })
                  }}
                >
                  <Plus size={14} />
                  新增标的
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function AssetRows({
  assets,
  groupOptions,
  onAssetChange,
  onAssetDelete,
  emptyText = "这个细则下还没有标的。",
}: {
  assets: Asset[]
  groupOptions: Array<{ bucket: PortfolioBucket; group: AssetGroup }>
  onAssetChange: (asset: Asset, overrides: Partial<AssetPayload>) => Promise<void>
  onAssetDelete: (asset: Asset) => Promise<void>
  emptyText?: string
}) {
  if (assets.length === 0) {
    return <div className="asset-tree-empty">{emptyText}</div>
  }

  return (
    <div className="asset-tree-rows">
      {assets.map((asset) => {
        const status = assetStatus(asset)
        const hasTransactions = asset.transaction_count > 0
        return (
          <div className="asset-tree-row" key={asset.id}>
            <div className="asset-tree-name">
              <WalletCards size={14} />
              <div>
                <strong>{asset.name}</strong>
                <span>
                  {asset.code ?? '无代码'} · {asset.exchange ?? '未识别市场'} · {asset.platform ?? asset.type} · 最新价 {formatMoney(asset.latest_price)}
                </span>
              </div>
            </div>
            <span className={`status-dot ${status.className}`}>{status.label}</span>
            <select
              aria-label={`设置 ${asset.name} 的组合归属`}
              value={asset.include_in_portfolio && asset.group_id ? String(asset.group_id) : 'none'}
              onChange={(event) => {
                const nextValue = event.target.value
                void onAssetChange(
                  asset,
                  nextValue === 'none'
                    ? { group_id: null, include_in_portfolio: false }
                    : { group_id: Number(nextValue), include_in_portfolio: true },
                )
              }}
            >
              <option value="none">不纳入组合</option>
              {groupOptions.map(({ bucket, group }) => (
                <option value={group.id} key={group.id}>
                  {bucket.name} / {group.name}
                </option>
              ))}
            </select>
            <div className="asset-tree-actions">
              {hasTransactions ? (
                <button
                  className="ghost-button"
                  type="button"
                  title={`已有 ${asset.transaction_count} 笔交易，不能删除`}
                  onClick={() => void onAssetChange(asset, { is_active: !asset.is_active })}
                >
                  {asset.is_active ? '停用' : '启用'}
                </button>
              ) : (
                <button
                  className="icon-button danger-button"
                  type="button"
                  aria-label={`删除 ${asset.name}`}
                  title={deletionTitle(asset)}
                  onClick={() => {
                    if (!window.confirm(deletionConfirmMessage(asset))) return
                    void onAssetDelete(asset)
                  }}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function deletionTitle(asset: Asset): string {
  if (asset.price_count > 0) {
    return `删除 ${asset.name}，并清理 ${asset.price_count} 条价格记录`
  }
  return `删除 ${asset.name}`
}

function deletionConfirmMessage(asset: Asset): string {
  if (asset.price_count > 0) {
    return `确定删除标的「${asset.name}」？将同时清理 ${asset.price_count} 条价格记录，此操作不可恢复。`
  }
  return `确定删除标的「${asset.name}」？此操作不可恢复。`
}

function assetStatus(asset: Asset): { label: string; className: string } {
  if (!asset.is_active) return { label: '已停用', className: 'status-inactive' }
  if (!asset.include_in_portfolio) return { label: '未纳入组合', className: 'status-watch' }
  if (!asset.group_id) return { label: '待归类', className: 'status-warning' }
  return { label: '已纳入组合', className: 'status-on' }
}

function BucketDirectForm({
  form,
  onChange,
  onCancel,
  onSubmit,
  mode,
}: {
  form: BucketFormState
  onChange: (next: BucketFormState) => void
  onCancel: () => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  mode: 'create' | 'edit'
}) {
  return (
    <form className="bucket-card-v2-header bucket-card-v2-header-edit" onSubmit={onSubmit}>
      <div className="bucket-eye">
        {mode === 'create' ? <Plus size={15} /> : <Layers3 size={15} />}
      </div>
      <div className="bucket-inline-fields">
        <label className="compact-field bucket-name-edit-field">
          <span>资产大类</span>
          <input
            required
            value={form.name}
            onChange={(e) => onChange({ ...form, name: e.target.value })}
            placeholder="股票 / 黄金"
            autoFocus
          />
        </label>
        <label className="compact-field">
          <span>目标 %</span>
          <input
            required
            type="number"
            min="0"
            max="100"
            step="0.01"
            value={form.targetWeight}
            onChange={(e) => onChange({ ...form, targetWeight: e.target.value })}
          />
        </label>
        <label className="compact-field compact-number-field">
          <span>排序</span>
          <input
            type="number"
            value={form.displayOrder}
            onChange={(e) => onChange({ ...form, displayOrder: e.target.value })}
          />
        </label>
      </div>
      <div className="bucket-actions-row">
        <button className="icon-button icon-button-active" type="submit" aria-label={mode === 'edit' ? '保存资产大类' : '新增资产大类'}>
          <Save size={15} />
        </button>
        <button className="icon-button" type="button" onClick={onCancel} aria-label="取消">
          <X size={15} />
        </button>
      </div>
    </form>
  )
}

function GroupDirectForm({
  form,
  structure,
  onChange,
  onCancel,
  onSubmit,
  mode,
}: {
  form: GroupFormState
  structure: PortfolioBucket[]
  onChange: (next: GroupFormState) => void
  onCancel: () => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  mode: 'create' | 'edit'
}) {
  return (
    <form className="group-row-v2 group-row-v2-edit" onSubmit={onSubmit}>
      <div className="group-inline-fields">
        <label className="compact-field">
          <span>大类</span>
          <select
            required
            value={form.bucketId}
            onChange={(e) => onChange({ ...form, bucketId: e.target.value })}
          >
            <option value="">选择大类</option>
            {structure.map((bucket) => (
              <option value={bucket.id} key={bucket.id}>
                {bucket.name}
              </option>
            ))}
          </select>
        </label>
        <label className="compact-field group-name-edit-field">
          <span>细则</span>
          <input
            required
            value={form.name}
            onChange={(e) => onChange({ ...form, name: e.target.value })}
            placeholder="美股指数 / A股"
            autoFocus
          />
        </label>
        <label className="compact-field compact-number-field">
          <span>目标 %</span>
          <input
            type="number"
            min="0"
            max="100"
            step="0.01"
            value={form.targetWeight}
            onChange={(e) => onChange({ ...form, targetWeight: e.target.value })}
          />
        </label>
        <label className="compact-field compact-number-field">
          <span>排序</span>
          <input
            type="number"
            value={form.displayOrder}
            onChange={(e) => onChange({ ...form, displayOrder: e.target.value })}
          />
        </label>
      </div>
      <div className="group-row-v2-actions">
        <button className="icon-button icon-button-active" type="submit" aria-label={mode === 'edit' ? '保存细则' : '新增细则'}>
          <Save size={15} />
        </button>
        <button className="icon-button" type="button" onClick={onCancel} aria-label="取消">
          <X size={15} />
        </button>
      </div>
    </form>
  )
}
