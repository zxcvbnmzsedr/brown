import {
  App as AntdApp,
  Button,
  Card,
  ConfigProvider,
  Form,
  Input,
  InputNumber,
  Layout,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  theme,
} from 'antd'
import type { TableColumnsType } from 'antd'
import {
  BankOutlined,
  CloudSyncOutlined,
  DatabaseOutlined,
  DollarOutlined,
  LoginOutlined,
  LogoutOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, clearAccessToken, getAccessToken } from './api'
import type {
  AdminUser,
  Instrument,
  InstrumentPayload,
  InstrumentType,
  PriceState,
  PriceStatus,
  TradingPlatform,
  TradingPlatformPayload,
  TradingPlatformType,
} from './types'

const instrumentTypeOptions: { label: string; value: InstrumentType }[] = [
  { label: '股票', value: 'stock' },
  { label: '基金', value: 'fund' },
  { label: 'ETF', value: 'etf' },
  { label: '债券', value: 'bond' },
  { label: '黄金', value: 'gold' },
  { label: '加密资产', value: 'crypto' },
]

const instrumentTypeLabels = Object.fromEntries(instrumentTypeOptions.map((item) => [item.value, item.label])) as Record<
  InstrumentType,
  string
>

const platformTypeOptions: { label: string; value: TradingPlatformType }[] = [
  { label: '券商', value: 'broker' },
  { label: '银行', value: 'bank' },
  { label: '基金平台', value: 'fund_platform' },
  { label: '支付/钱包', value: 'payment' },
  { label: '加密交易所', value: 'crypto_exchange' },
  { label: '其他', value: 'other' },
]

const platformTypeLabels = Object.fromEntries(platformTypeOptions.map((item) => [item.value, item.label])) as Record<
  TradingPlatformType,
  string
>

const priceStateLabels: Record<PriceState, string> = {
  fresh: '已更新',
  stale: '已过期',
  missing: '缺价格',
}

const priceStateColors: Record<PriceState, string> = {
  fresh: 'green',
  stale: 'orange',
  missing: 'red',
}

function AuthPanel({ onAuthenticated }: { onAuthenticated: (admin: AdminUser) => void }) {
  const { message } = AntdApp.useApp()
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm<{ email: string; password: string }>()

  async function submit() {
    const values = await form.validateFields()
    setLoading(true)
    try {
      const result = await api.login(values.email, values.password)
      message.success('登录成功')
      onAuthenticated(result.admin)
    } catch (caught) {
      message.error(caught instanceof Error ? caught.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="authPage">
      <Card className="authCard">
        <Typography.Title level={2}>Brown Admin</Typography.Title>
        <Typography.Text type="secondary">运营后台仅维护标的、交易平台和价格基础数据。</Typography.Text>
        <Form form={form} layout="vertical" onFinish={() => void submit()} className="authForm">
          <Form.Item name="email" label="管理员邮箱" rules={[{ required: true, type: 'email' }]}>
            <Input autoComplete="email" placeholder="admin@example.com" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" icon={<LoginOutlined />} loading={loading} block>
            登录
          </Button>
        </Form>
      </Card>
    </main>
  )
}

function InstrumentsPanel() {
  const { message } = AntdApp.useApp()
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [items, setItems] = useState<Instrument[]>([])
  const [editing, setEditing] = useState<Instrument | null>(null)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm<InstrumentPayload>()
  const [searchForm] = Form.useForm<{ q?: string; instrument_type?: InstrumentType; market?: string }>()
  const [syncForm] = Form.useForm<{ query: string; limit: number }>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await api.listInstruments({ ...searchForm.getFieldsValue(), include_inactive: true }))
    } finally {
      setLoading(false)
    }
  }, [searchForm])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [load])

  function openCreate() {
    setEditing(null)
    form.setFieldsValue({
      name: '',
      type: 'etf',
      code: null,
      exchange: null,
      currency: 'CNY',
      source: 'manual',
      is_active: true,
    })
    setOpen(true)
  }

  function openEdit(instrument: Instrument) {
    setEditing(instrument)
    form.setFieldsValue({
      name: instrument.name,
      type: instrument.type,
      code: instrument.code,
      exchange: instrument.exchange,
      currency: instrument.currency,
      source: instrument.source,
      is_active: instrument.is_active,
    })
    setOpen(true)
  }

  async function saveInstrument() {
    const values = await form.validateFields()
    const payload = {
      ...values,
      code: values.code?.trim() || null,
      exchange: values.exchange?.trim().toUpperCase() || null,
      currency: values.currency?.trim().toUpperCase() || 'CNY',
      source: values.source?.trim() || null,
    }
    if (editing) {
      await api.updateInstrument(editing.id, payload)
      message.success('标的已更新')
    } else {
      await api.createInstrument(payload)
      message.success('标的已创建')
    }
    setOpen(false)
    await load()
  }

  const columns: TableColumnsType<Instrument> = [
    { title: '名称', dataIndex: 'name', fixed: 'left', width: 190 },
    { title: '代码', dataIndex: 'code', width: 110, render: (value) => value || '-' },
    { title: '市场', dataIndex: 'exchange', width: 90, render: (value) => value || '-' },
    { title: '类型', dataIndex: 'type', width: 110, render: (value: InstrumentType) => instrumentTypeLabels[value] ?? value },
    { title: '币种', dataIndex: 'currency', width: 90 },
    { title: '最新价', dataIndex: 'latest_price', width: 110, render: (value) => value ?? '-' },
    { title: '价格日', dataIndex: 'price_date', width: 120, render: (value) => value || '-' },
    {
      title: '状态',
      width: 100,
      render: (_, record) => (record.is_active ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
    },
    {
      title: '操作',
      width: 170,
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button
            size="small"
            onClick={async () => {
              await api.toggleInstrument(record.id)
              message.success(record.is_active ? '已停用' : '已启用')
              await load()
            }}
          >
            {record.is_active ? '停用' : '启用'}
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <Typography.Title level={3}>标的库</Typography.Title>
          <Typography.Text type="secondary">只维护可交易、可报价标的；现金不进入标的库。</Typography.Text>
        </div>
        <Button icon={<PlusOutlined />} type="primary" onClick={openCreate}>
          新增标的
        </Button>
      </div>
      <Form form={searchForm} layout="inline" className="toolbar" onFinish={() => void load()}>
        <Form.Item name="q">
          <Input prefix={<SearchOutlined />} placeholder="名称/代码" allowClear />
        </Form.Item>
        <Form.Item name="instrument_type">
          <Select placeholder="类型" allowClear options={instrumentTypeOptions} className="filterSelect" />
        </Form.Item>
        <Form.Item name="market">
          <Input placeholder="市场，如 SH/SZ" className="filterInput" />
        </Form.Item>
        <Form.Item>
          <Button htmlType="submit">搜索</Button>
        </Form.Item>
        <Form.Item>
          <Button
            onClick={async () => {
              searchForm.resetFields()
              await load()
            }}
          >
            重置
          </Button>
        </Form.Item>
      </Form>
      <Form form={syncForm} layout="inline" className="toolbar" initialValues={{ limit: 20 }}>
        <Form.Item name="query" rules={[{ required: true, min: 2 }]}>
          <Input placeholder="输入关键词同步，例如 510300" className="syncInput" />
        </Form.Item>
        <Form.Item name="limit">
          <InputNumber min={1} max={50} />
        </Form.Item>
        <Form.Item>
          <Button
            icon={<CloudSyncOutlined />}
            loading={syncing}
            onClick={async () => {
              const values = await syncForm.validateFields()
              setSyncing(true)
              try {
                const result = await api.syncInstruments(values.query, values.limit)
                if (result.errors.length) {
                  message.warning(result.errors.join('；'))
                } else {
                  message.success(`同步完成：新增 ${result.imported}，跳过 ${result.skipped}`)
                }
                await load()
              } finally {
                setSyncing(false)
              }
            }}
          >
            同步标的
          </Button>
        </Form.Item>
      </Form>
      <Table<Instrument> rowKey="id" loading={loading} columns={columns} dataSource={items} pagination={{ pageSize: 12 }} scroll={{ x: 1180 }} />
      <Modal title={editing ? '编辑标的' : '新增标的'} open={open} onCancel={() => setOpen(false)} onOk={() => void saveInstrument()} destroyOnHidden>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label="类型" rules={[{ required: true }]}>
            <Select options={instrumentTypeOptions} />
          </Form.Item>
          <Form.Item name="code" label="代码">
            <Input />
          </Form.Item>
          <Form.Item name="exchange" label="市场">
            <Input placeholder="SH / SZ / NASDAQ / HK" />
          </Form.Item>
          <Form.Item name="currency" label="币种" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="source" label="来源">
            <Input />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  )
}

function PlatformsPanel() {
  const { message } = AntdApp.useApp()
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<TradingPlatform[]>([])
  const [editing, setEditing] = useState<TradingPlatform | null>(null)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm<TradingPlatformPayload>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await api.listTradingPlatforms())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [load])

  function openCreate() {
    setEditing(null)
    form.setFieldsValue({ name: '', type: 'broker', account_type: null, display_order: 0, is_active: true })
    setOpen(true)
  }

  function openEdit(platform: TradingPlatform) {
    setEditing(platform)
    form.setFieldsValue({
      name: platform.name,
      type: platform.type,
      account_type: platform.account_type,
      display_order: platform.display_order,
      is_active: platform.is_active,
    })
    setOpen(true)
  }

  async function savePlatform() {
    const values = await form.validateFields()
    const payload = { ...values, account_type: values.account_type?.trim() || null }
    if (editing) {
      await api.updateTradingPlatform(editing.id, payload)
      message.success('平台已更新')
    } else {
      await api.createTradingPlatform(payload)
      message.success('平台已创建')
    }
    setOpen(false)
    await load()
  }

  const columns: TableColumnsType<TradingPlatform> = [
    { title: '名称', dataIndex: 'name' },
    { title: '类型', dataIndex: 'type', width: 150, render: (value: TradingPlatformType) => platformTypeLabels[value] ?? value },
    { title: '账户类型', dataIndex: 'account_type', render: (value) => value || '-' },
    { title: '排序', dataIndex: 'display_order', width: 90 },
    {
      title: '状态',
      width: 100,
      render: (_, record) => (record.is_active ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
    },
    {
      title: '操作',
      width: 170,
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Button
            size="small"
            onClick={async () => {
              await api.toggleTradingPlatform(record.id)
              message.success(record.is_active ? '已停用' : '已启用')
              await load()
            }}
          >
            {record.is_active ? '停用' : '启用'}
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <Typography.Title level={3}>交易平台</Typography.Title>
          <Typography.Text type="secondary">覆盖券商、银行、基金平台和支付钱包，供用户创建投资账户或现金账户。</Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增平台
        </Button>
      </div>
      <Table<TradingPlatform> rowKey="id" loading={loading} columns={columns} dataSource={items} pagination={false} />
      <Modal title={editing ? '编辑交易平台' : '新增交易平台'} open={open} onCancel={() => setOpen(false)} onOk={() => void savePlatform()} destroyOnHidden>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label="类型" rules={[{ required: true }]}>
            <Select options={platformTypeOptions} />
          </Form.Item>
          <Form.Item name="account_type" label="账户类型">
            <Input placeholder="普通证券账户 / 储蓄卡 / 基金账户" />
          </Form.Item>
          <Form.Item name="display_order" label="排序">
            <InputNumber min={0} className="fullWidth" />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  )
}

function PricesPanel() {
  const { message } = AntdApp.useApp()
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [items, setItems] = useState<PriceStatus[]>([])
  const [editing, setEditing] = useState<PriceStatus | null>(null)
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm<{ price: number; date?: string }>()
  const [searchForm] = Form.useForm<{ q?: string; price_state?: PriceState }>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await api.listPriceStatus(searchForm.getFieldsValue()))
    } finally {
      setLoading(false)
    }
  }, [searchForm])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [load])

  const columns: TableColumnsType<PriceStatus> = [
    { title: '标的', dataIndex: 'instrument_name', fixed: 'left', width: 180 },
    { title: '代码', dataIndex: 'instrument_code', width: 110, render: (value) => value || '-' },
    { title: '市场', dataIndex: 'instrument_exchange', width: 90, render: (value) => value || '-' },
    { title: '类型', dataIndex: 'instrument_type', width: 110, render: (value: InstrumentType) => instrumentTypeLabels[value] ?? value },
    { title: '最新价格', dataIndex: 'latest_price', width: 120, render: (value) => value ?? '-' },
    { title: '价格日期', dataIndex: 'price_date', width: 120, render: (value) => value || '-' },
    {
      title: '状态',
      width: 110,
      render: (_, record) => <Tag color={priceStateColors[record.price_state]}>{priceStateLabels[record.price_state]}</Tag>,
    },
    {
      title: '操作',
      width: 110,
      render: (_, record) => (
        <Button
          size="small"
          onClick={() => {
            setEditing(record)
            form.setFieldsValue({ price: record.latest_price ?? 0, date: record.price_date ?? undefined })
            setOpen(true)
          }}
        >
          手动价格
        </Button>
      ),
    },
  ]

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <Typography.Title level={3}>价格管理</Typography.Title>
          <Typography.Text type="secondary">价格只服务标的；现金余额由用户现金账户维护。</Typography.Text>
        </div>
        <Button
          type="primary"
          icon={<CloudSyncOutlined />}
          loading={fetching}
          onClick={async () => {
            setFetching(true)
            try {
              const result = await api.fetchPrices()
              if (result.errors.length) {
                message.warning(result.errors.join('；'))
              } else {
                message.success(`批量抓取完成：更新 ${result.updated}/${result.target_count}`)
              }
              await load()
            } finally {
              setFetching(false)
            }
          }}
        >
          批量抓取
        </Button>
      </div>
      <Form form={searchForm} layout="inline" className="toolbar" onFinish={() => void load()}>
        <Form.Item name="q">
          <Input prefix={<SearchOutlined />} placeholder="名称/代码" allowClear />
        </Form.Item>
        <Form.Item name="price_state">
          <Select
            placeholder="价格状态"
            allowClear
            className="filterSelect"
            options={Object.entries(priceStateLabels).map(([value, label]) => ({ value, label }))}
          />
        </Form.Item>
        <Form.Item>
          <Button htmlType="submit">搜索</Button>
        </Form.Item>
        <Form.Item>
          <Button
            onClick={async () => {
              searchForm.resetFields()
              await load()
            }}
          >
            重置
          </Button>
        </Form.Item>
      </Form>
      <Table<PriceStatus> rowKey="instrument_id" loading={loading} columns={columns} dataSource={items} pagination={{ pageSize: 12 }} scroll={{ x: 960 }} />
      <Modal
        title={editing ? `手动价格：${editing.instrument_name}` : '手动价格'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={async () => {
          if (!editing) return
          const values = await form.validateFields()
          await api.updatePrice(editing.instrument_id, values.price, values.date)
          message.success('价格已保存')
          setOpen(false)
          await load()
        }}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="price" label="价格" rules={[{ required: true }]}>
            <InputNumber min={0} className="fullWidth" />
          </Form.Item>
          <Form.Item name="date" label="日期">
            <Input placeholder="YYYY-MM-DD，留空为今天" />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  )
}

function AdminShell({ admin, onLogout }: { admin: AdminUser; onLogout: () => void }) {
  const tabs = useMemo(
    () => [
      { key: 'instruments', label: '标的库', icon: <DatabaseOutlined />, children: <InstrumentsPanel /> },
      { key: 'platforms', label: '交易平台', icon: <BankOutlined />, children: <PlatformsPanel /> },
      { key: 'prices', label: '价格管理', icon: <DollarOutlined />, children: <PricesPanel /> },
    ],
    [],
  )

  return (
    <Layout className="shell">
      <Layout.Sider width={248} theme="light" className="sider">
        <div className="brand">
          <Typography.Title level={4}>Brown Admin</Typography.Title>
          <Typography.Text type="secondary">运营基础库</Typography.Text>
        </div>
      </Layout.Sider>
      <Layout.Content className="content">
        <div className="topbar">
          <div>
            <Typography.Title level={2}>运营后台</Typography.Title>
            <Typography.Text type="secondary">维护全局标的、交易平台和价格。</Typography.Text>
          </div>
          <Space>
            <Typography.Text>{admin.email}</Typography.Text>
            <Button icon={<LogoutOutlined />} onClick={onLogout}>
              退出
            </Button>
          </Space>
        </div>
        <Tabs items={tabs} tabPlacement="start" className="workspaceTabs" />
      </Layout.Content>
    </Layout>
  )
}

function AdminApp() {
  const [admin, setAdmin] = useState<AdminUser | null>(null)
  const [loading, setLoading] = useState(() => Boolean(getAccessToken()))

  useEffect(() => {
    if (!getAccessToken()) return
    let active = true
    api
      .getMe()
      .then((currentAdmin) => {
        if (active) setAdmin(currentAdmin)
      })
      .catch(() => {
        clearAccessToken()
        if (active) setAdmin(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return <main className="loadingPage">加载中...</main>
  }

  if (!admin) {
    return <AuthPanel onAuthenticated={setAdmin} />
  }

  return (
    <AdminShell
      admin={admin}
      onLogout={() => {
        clearAccessToken()
        setAdmin(null)
      }}
    />
  )
}

export default function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#2458d3',
          borderRadius: 8,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", "Segoe UI", system-ui, sans-serif',
        },
      }}
    >
      <AntdApp>
        <AdminApp />
      </AntdApp>
    </ConfigProvider>
  )
}
