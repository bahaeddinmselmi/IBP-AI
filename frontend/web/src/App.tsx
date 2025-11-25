import React, { useState } from 'react';
import { ResponsiveContainer, AreaChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

type Page = 'dashboard' | 'scenario' | 'data';

const NAV_ITEMS: Array<{ id: Page; label: string; hint: string }> = [
  {
    id: 'dashboard',
    label: 'Control Tower',
    hint: 'Forecast & supply overview',
  },
  { id: 'scenario', label: 'Scenario Lab', hint: 'Compare what-if outcomes' },
  { id: 'data', label: 'Data Import', hint: 'Manage source datasets' },
];

type ForecastPoint = {
  sku: string;
  date: string;
  mean: number;
  q10: number;
  q50: number;
  q90: number;
};

type ForecastResponse = {
  forecast_id: string;
  points: ForecastPoint[];
  metadata: {
    model_name: string;
    model_version: string;
    per_sku_model?: Record<string, string>;
  };
  metrics?: Record<string, number>;
};

type PlanResponse = {
  plan_id: string;
  forecast_id: string;
  orders: any[];
  production: any[];
  kpis: { name: string; value: number; unit?: string | null }[];
};

type ExplainResponse = {
  forecast_id: string;
  global_importance: { feature: string; importance: number; direction: string }[];
  external_summary?: string | null;
};

type ScenarioResponse = {
  scenario_id: string;
  forecast_id: string;
  plan_id?: string | null;
  name?: string | null;
  narrative?: string | null;
  kpis: { name: string; base: number; scenario: number; delta: number; unit?: string | null }[];
};

type ScenarioSummary = {
  scenario_id: string;
  forecast_id: string;
  plan_id?: string | null;
  name?: string | null;
};

type ScenarioListResponse = {
  scenarios: ScenarioSummary[];
};

type DatasetType =
  | 'sales'
  | 'inventory'
  | 'production'
  | 'purchase_orders'
  | 'master_data'
  | 'external_signals';

const DATASET_LABELS: Record<DatasetType, string> = {
  sales: 'Sales',
  inventory: 'Inventory',
  production: 'Production',
  purchase_orders: 'Purchase orders',
  master_data: 'Master data',
  external_signals: 'External signals',
};

type DatasetPreview = {
  dataset_type: DatasetType;
  rows: number;
  columns: string[];
  preview?: any[];
  path: string;
  schema?: { name: string; dtype: string; role: string }[];
  warnings?: string[];
};

const DATASET_KEYWORDS: Record<DatasetType, string[]> = {
  sales: ['quantity', 'qty', 'units', 'order', 'product', 'sku', 'customer', 'totalprice', 'date', 'amount', 'volume', 'sales'],
  inventory: ['stock', 'onhand', 'inventory', 'warehouse', 'location', 'sku', 'reorder', 'quantity'],
  production: ['production', 'line', 'capacity', 'machine', 'shift', 'schedule', 'quantity'],
  purchase_orders: ['po', 'purchase', 'supplier', 'eta', 'orderdate', 'quantity', 'location', 'vendor'],
  master_data: ['description', 'category', 'uom', 'segment', 'attribute', 'name', 'id'],
  external_signals: ['signal', 'trend', 'index', 'score', 'weather', 'holiday', 'sentiment', 'date'],
};

const normalizeColumnName = (name: string) => name.toLowerCase().replace(/[\s_\-]/g, '');

function guessDatasetTypeFromColumns(columns: string[]): DatasetType | null {
  if (!columns || columns.length === 0) {
    return null;
  }

  const normalized = columns.map(normalizeColumnName);
  let bestType: DatasetType | null = null;
  let bestScore = 0;

  (Object.entries(DATASET_KEYWORDS) as Array<[DatasetType, string[]]>).forEach(([type, keywords]) => {
    let score = 0;
    keywords.forEach((keyword) => {
      if (normalized.some((col) => col.includes(keyword))) {
        score += 1;
      }
    });
    if (score > bestScore) {
      bestScore = score;
      bestType = type;
    }
  });

  if (!bestType) {
    return null;
  }

  if (bestScore < 2) {
    const hasQuantityLike = normalized.some(
      (col) => col.includes('quantity') || col.includes('qty') || col.includes('units') || col.includes('amount') || col.includes('volume'),
    );
    const hasDate = normalized.some((col) => col.includes('date') || col.includes('time') || col.includes('period'));
    const hasSalesKeywords = normalized.some((col) => col.includes('sales') || col.includes('order') || col.includes('customer'));
    if (bestType === 'sales' && hasQuantityLike && (hasDate || hasSalesKeywords)) {
      return 'sales';
    }
    return null;
  }

  return bestType;
}

function guessDatasetTypeFromFileName(fileName: string): DatasetType | null {
  const lower = fileName.toLowerCase();
  if (lower.includes('sales') || lower.includes('sell')) return 'sales';
  if (lower.includes('inventory') || lower.includes('stock')) return 'inventory';
  if (lower.includes('production') || lower.includes('manufacturing')) return 'production';
  if (lower.includes('purchase') || lower.includes('po_') || lower.includes('vendor'))
    return 'purchase_orders';
  if (lower.includes('master') || lower.includes('catalog')) return 'master_data';
  if (lower.includes('signal') || lower.includes('external') || lower.includes('macro'))
    return 'external_signals';
  return null;
}

type CopilotContext = 'forecast' | 'plan' | 'scenario' | 'data';

type CopilotQueryResponse = {
  answer: string;
  suggested_actions: string[];
  used_context: Record<string, any>;
 };

 type CopilotMessage = {
  role: 'user' | 'assistant';
  text: string;
 };

 async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  baseUrl: string,
  apiKey: string,
 ): Promise<T> {
  const url = `${baseUrl.replace(/\/$/, '')}${path}`;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'X-API-Key': apiKey,
    ...(options.headers || {}),
  };

  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }
  return (await response.json()) as T;
 }

 async function apiUpload<T = any>(
  path: string,
  form: FormData,
  baseUrl: string,
  apiKey: string,
 ): Promise<T> {
  const url = `${baseUrl.replace(/\/$/, '')}${path}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'X-API-Key': apiKey,
    },
    body: form,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }

  return (await response.json()) as T;
 }

 const App: React.FC = () => {
  const [page, setPage] = useState<Page>('dashboard');
  const [apiBaseUrl, setApiBaseUrl] = useState('http://localhost:8000');
  const [apiKey, setApiKey] = useState('dev-api-key-change-me');

  const [skuInput, setSkuInput] = useState('SKU-001,SKU-002,SKU-003');
  const [location, setLocation] = useState('WH-1');
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState('2025-01-30');
  const [granularity, setGranularity] = useState<'D' | 'W' | 'M'>('D');
  const [forecastModel, setForecastModel] = useState<'auto' | 'baseline' | 'arima' | 'prophet' | 'xgboost'>('auto');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [explain, setExplain] = useState<ExplainResponse | null>(null);
  const [scenario, setScenario] = useState<ScenarioResponse | null>(null);

  const [scenarioDemandFactor, setScenarioDemandFactor] = useState(1.2);

  const [scenarioList, setScenarioList] = useState<ScenarioSummary[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<ScenarioResponse | null>(null);
  const [scenarioDetailLoading, setScenarioDetailLoading] = useState(false);

  const [datasetType, setDatasetType] = useState<DatasetType>('sales');
  const [dataPreview, setDataPreview] = useState<DatasetPreview | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  const [copilotInput, setCopilotInput] = useState('');
  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([]);
  const [copilotActions, setCopilotActions] = useState<string[]>([]);
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotContextForecast, setCopilotContextForecast] = useState(true);
  const [copilotContextPlan, setCopilotContextPlan] = useState(true);
  const [copilotContextScenario, setCopilotContextScenario] = useState(true);
  const [copilotContextData, setCopilotContextData] = useState(true);

  const canCallApi = apiBaseUrl.trim().length > 0 && apiKey.trim().length > 0;
  const datasetTypeLabel = DATASET_LABELS[datasetType];

  function maybeAdoptSalesDefaults(preview: DatasetPreview) {
   if (preview.dataset_type !== 'sales' || !preview.preview || preview.preview.length === 0) {
    return;
   }

   const columns = preview.columns;
   const norm = (s: string) => s.toLowerCase().replace(/\s|_/g, '');

   const findCol = (candidates: string[]): string | null => {
    for (const cand of candidates) {
     const key = norm(cand);
     const found = columns.find((col) => norm(col) === key || norm(col).includes(key));
     if (found) return found;
    }
    return null;
   };

   const dateCol = findCol(['date', 'order_date', 'orderdate', 'orderdate', 'transactiondate', 'saledate', 'time', 'period']);
   const skuCol = findCol(['sku', 'product', 'item', 'product_id', 'productid', 'productname', 'itemid', 'itemname']);

   if (skuCol) {
    const skus = Array.from(
     new Set(
      preview.preview
       .map((row: any) => row[skuCol])
       .filter((v) => typeof v === 'string' && v.trim().length > 0),
     ),
    ).slice(0, 20);
    if (skus.length > 0) {
     setSkuInput(skus.join(','));
    }
   }

   if (dateCol) {
    const dates = preview.preview
     .map((row: any) => new Date(row[dateCol]))
     .filter((d) => !Number.isNaN(d.getTime()));
    if (dates.length > 0) {
     const min = new Date(Math.min(...dates.map((d) => d.getTime())));
     const max = new Date(Math.max(...dates.map((d) => d.getTime())));
     const toISO = (d: Date) => d.toISOString().slice(0, 10);
     setStartDate(toISO(min));
     setEndDate(toISO(max));
    }
   }

   // Default to all locations when using an uploaded Sales dataset so that
   // forecasting is based on the full Region coverage unless the user
   // explicitly filters.
   setLocation('');
  }

  async function handleCreateForecast() {
   setError(null);
   setExplain(null);
   setScenario(null);
   setLoading(true);
   try {
    const sku_list = skuInput
     .split(',')
     .map((s) => s.trim())
     .filter((s) => s.length > 0);

    const forced_model =
     forecastModel === 'auto'
      ? null
      : forecastModel === 'baseline'
      ? 'stub'
      : forecastModel;

    const body = {
     sku_list,
     start_date: startDate,
     end_date: endDate,
     granularity,
     location: location || null,
     forced_model,
    };

    const data = await apiRequest<ForecastResponse>('/api/v1/forecast', {
     method: 'POST',
     body: JSON.stringify(body),
    }, apiBaseUrl, apiKey);

    setForecast(data);
    setPlan(null);
   } catch (e: any) {
    setError(e.message ?? String(e));
   } finally {
    setLoading(false);
   }
  }

  async function handleCopilotAsk() {
   const question = copilotInput.trim();
   if (!question) return;
   const contexts: CopilotContext[] = [];
   if (copilotContextForecast) contexts.push('forecast');
   if (copilotContextPlan) contexts.push('plan');
   if (copilotContextScenario) contexts.push('scenario');
   if (copilotContextData) contexts.push('data');
   if (contexts.length === 0) return;

   setCopilotLoading(true);
   setCopilotActions([]);
   setError(null);
   setCopilotInput('');
   setCopilotMessages((prev) => [...prev, { role: 'user', text: question }]);
   try {
    const body = {
     query: question,
     contexts,
     forecast_id: forecast?.forecast_id ?? null,
     plan_id: plan?.plan_id ?? null,
     scenario_id: selectedScenarioId ?? scenario?.scenario_id ?? null,
     dataset_type: copilotContextData ? datasetType : undefined,
    };

    const data = await apiRequest<CopilotQueryResponse>(
     '/api/v1/copilot/query',
     {
      method: 'POST',
      body: JSON.stringify(body),
     },
     apiBaseUrl,
     apiKey,
    );
    setCopilotMessages((prev) => [...prev, { role: 'assistant', text: data.answer }]);
    setCopilotActions(data.suggested_actions ?? []);
   } catch (e: any) {
    setError(e.message ?? String(e));
   } finally {
    setCopilotLoading(false);
   }
  }

  async function fetchScenarioDetails(id: string) {
   setError(null);
   setScenarioDetailLoading(true);
   try {
    const data = await apiRequest<ScenarioResponse>(
     `/api/v1/scenario/${id}`,
     {},
     apiBaseUrl,
     apiKey,
    );
    setSelectedScenarioId(id);
    setSelectedScenario(data);
   } catch (e: any) {
    setError(e.message ?? String(e));
   } finally {
    setScenarioDetailLoading(false);
   }
  }

  async function handleGeneratePlan() {
   if (!forecast) return;
   setError(null);
   setLoading(true);
   try {
    const body = {
     forecast_id: forecast.forecast_id,
     objective: 'service_level',
     constraints: {
      target_service_level: 0.95,
      max_days_of_cover: 90,
      min_days_of_cover: 0,
      lead_time_days: 10,
     },
     location: location || null,
    };

    const data = await apiRequest<PlanResponse>('/api/v1/plan/generate', {
     method: 'POST',
     body: JSON.stringify(body),
    }, apiBaseUrl, apiKey);

    setPlan(data);
   } catch (e: any) {
    setError(e.message ?? String(e));
   } finally {
    setLoading(false);
   }
  }

  async function handleExplain() {
   if (!forecast) return;
   setError(null);
   setLoading(true);
   try {
    const data = await apiRequest<ExplainResponse>(
     `/api/v1/explain/${forecast.forecast_id}`,
     {},
     apiBaseUrl,
     apiKey,
    );
    setExplain(data);
   } catch (e: any) {
    setError(e.message ?? String(e));
   } finally {
    setLoading(false);
   }
  }

  async function handleScenario() {
   if (!forecast || !plan) return;
   setError(null);
   setLoading(true);
   try {
    const body = {
     forecast_id: forecast.forecast_id,
     plan_id: plan.plan_id,
     name: `Demand x${scenarioDemandFactor.toFixed(2)}`,
     shocks: [
      {
       type: 'demand',
       sku: null,
       location: null,
       start_date: startDate,
       end_date: endDate,
       factor: scenarioDemandFactor,
       delta: 0.0,
      },
     ],
    };

    const data = await apiRequest<ScenarioResponse>('/api/v1/scenario', {
     method: 'POST',
     body: JSON.stringify(body),
    }, apiBaseUrl, apiKey);

    setScenario(data);
   } catch (e: any) {
    setError(e.message ?? String(e));
   } finally {
    setLoading(false);
   }
  }

  function renderDashboard() {
   const forecastPoints = forecast?.points ?? [];
   const skuTotals =
    forecastPoints.length > 0
     ? Object.entries(
        forecastPoints.reduce<Record<string, number>>((acc, p) => {
         acc[p.sku] = (acc[p.sku] || 0) + p.mean;
         return acc;
        }, {}),
       )
     : [];

   const topSkuTotals = [...skuTotals].sort((a, b) => b[1] - a[1]).slice(0, 5);
   const maxSkuTotal =
    topSkuTotals.length > 0 ? Math.max(...topSkuTotals.map(([, v]) => v)) : 1;

   const dateAggregates =
    forecastPoints.length > 0
     ? Object.entries(
        forecastPoints.reduce<
         Record<string, { mean: number; q10: number; q90: number }>
        >((acc, point) => {
         const current =
          acc[point.date] ?? { mean: 0, q10: 0, q90: 0 };
         current.mean += point.mean;
         current.q10 += point.q10;
         current.q90 += point.q90;
         acc[point.date] = current;
         return acc;
        }, {}),
       ).sort((a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime())
     : [];

   const chartData =
    dateAggregates.length > 0
     ? dateAggregates.map(([date, agg]) => ({
        date,
        label: date.slice(5),
        mean: agg.mean,
        q10: agg.q10,
        q90: agg.q90,
       }))
     : [];

  const skuMetrics: Record<string, { mape?: number; mae?: number }> = {};
  if (forecast?.metrics && forecast.metadata.per_sku_model) {
   // Backend stores per-model metrics using prefixes: arima_*, prophet_*, xgb_*
   const metricPrefixes = ['arima', 'prophet', 'xgb'];
   Object.keys(forecast.metadata.per_sku_model).forEach((sku) => {
    let bestMape: number | undefined;
    let bestMae: number | undefined;
    for (const prefix of metricPrefixes) {
     const mapeKey = `${sku}.${prefix}_mape`;
     const maeKey = `${sku}.${prefix}_mae`;
     const mapeVal = forecast.metrics?.[mapeKey];
     if (mapeVal != null && Number.isFinite(mapeVal)) {
      if (bestMape === undefined || mapeVal < bestMape) {
       bestMape = mapeVal;
       bestMae = forecast.metrics?.[maeKey];
      }
     }
    }
    skuMetrics[sku] = { mape: bestMape, mae: bestMae };
   });
  }

   const horizonPeriods = dateAggregates.length;
   const maxBandValue =
    dateAggregates.length > 0
     ? Math.max(
        ...dateAggregates.map(([, agg]) =>
         Math.max(agg.q90 || agg.mean, agg.mean),
        ),
       )
     : 1;

   const minBandValue =
    dateAggregates.length > 0
     ? Math.min(
        ...dateAggregates.map(([, agg]) =>
         Math.min(agg.q10 || agg.mean, agg.mean),
        ),
       )
     : 0;

   const totalVolume = forecastPoints.reduce((sum, p) => sum + p.mean, 0);
   const uniqueSkuCount = skuTotals.length;
   const numberFormatter = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 0,
   });

   const volumeLabel =
    totalVolume > 0 ? `${numberFormatter.format(totalVolume)} units` : '—';
   const horizonLabel =
    forecast && horizonPeriods > 0
     ? `${horizonPeriods} period${horizonPeriods === 1 ? '' : 's'} · ${uniqueSkuCount} SKU${
        uniqueSkuCount === 1 ? '' : 's'
       }`
     : 'Generate a forecast to populate.';

   const planVolumeKpi = plan?.kpis.find((k) =>
    k.name.toLowerCase().includes('total'),
   );
   const planServiceLevelKpi = plan?.kpis.find((k) =>
    k.name.toLowerCase().includes('service level'),
   );

   const planVolumeLabel = planVolumeKpi
    ? `${numberFormatter.format(planVolumeKpi.value)} ${planVolumeKpi.unit?.trim() || 'units'}`
    : 'Generate a plan to populate.';

   let serviceLevelLabel = '—';
   if (planServiceLevelKpi) {
    if (planServiceLevelKpi.unit && planServiceLevelKpi.unit.trim()) {
     serviceLevelLabel = `${planServiceLevelKpi.value.toFixed(2)} ${planServiceLevelKpi.unit.trim()}`;
    } else if (planServiceLevelKpi.value <= 1.5) {
     serviceLevelLabel = `${(planServiceLevelKpi.value * 100).toFixed(1)}%`;
    } else {
     serviceLevelLabel = planServiceLevelKpi.value.toFixed(1);
    }
   }

   const scenarioTotal =
    scenarioList.length > 0 ? scenarioList.length : scenario ? 1 : 0;
   const scenarioLabel =
    scenarioTotal > 0 ? `${scenarioTotal} active` : 'No scenarios yet';
   const scenarioSubLabel =
    scenario?.name
     ? `${scenario.name} is the latest run.`
     : 'Run a quick scenario to stress-test the plan.';

   const activeDatasetLabel = DATASET_LABELS[dataPreview?.dataset_type ?? datasetType];
  const datasetDescriptor = dataPreview
    ? `${numberFormatter.format(dataPreview.rows)} rows · ${dataPreview.columns.length} columns`
    : 'Preview a dataset to populate defaults.';

   return (
    <div className="space-y-6">
     <div className="card card-header">
      <div>
       <h1 className="text-2xl font-bold text-slate-900">Forecast & Supply Planning</h1>
       <p className="text-sm text-slate-500 mt-1">
        Monitor demand forecasts, align supply plans, and experiment with scenarios
       </p>
      </div>
      {forecast && (
       <div className="badge badge-success">
        <span className="h-2 w-2 rounded-full bg-emerald-500" />
        Forecast Ready
       </div>
      )}
     </div>

     <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="card card-body">
       <div className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-3">Forecast Volume</div>
       <div className="text-4xl font-bold text-blue-600 mb-2">{volumeLabel}</div>
       <div className="text-sm text-slate-700 font-medium">{horizonLabel}</div>
      </div>

      <div className="card card-body">
       <div className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-3">Plan Health</div>
       <div className="text-4xl font-bold text-emerald-600 mb-2">{serviceLevelLabel}</div>
       <div className="text-sm text-slate-700 font-medium">{planVolumeLabel}</div>
      </div>

      <div className="card card-body">
       <div className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-3">Scenarios</div>
       <div className="text-4xl font-bold text-amber-600 mb-2">{scenarioLabel}</div>
       <div className="text-sm text-slate-700 font-medium">{scenarioSubLabel}</div>
      </div>

      <div className="card card-body">
       <div className="text-sm font-semibold text-slate-700 uppercase tracking-wider mb-3">Data Source</div>
       <div className="text-4xl font-bold text-purple-600 mb-2">{activeDatasetLabel}</div>
       <div className="text-sm text-slate-700 font-medium">{datasetDescriptor}</div>
      </div>
     </div>

     <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="card">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">API Settings</h3>
       </div>
       <div className="card-body space-y-4">
        <div>
         <label className="block text-sm font-medium text-slate-700 mb-1">API Base URL</label>
         <input
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          value={apiBaseUrl}
          onChange={(e) => setApiBaseUrl(e.target.value)}
          placeholder="http://localhost:8000"
         />
        </div>
        <div>
         <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
         <input
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="••••••••••••"
         />
        </div>
        {!canCallApi && (
         <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          Configure API settings to enable operations.
         </div>
        )}
       </div>
      </div>

      <div className="card">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">Generate Forecast</h3>
       </div>
       <div className="card-body space-y-4">
        <div>
         <label className="block text-sm font-medium text-slate-700 mb-1">SKUs (comma-separated)</label>
         <input
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          value={skuInput}
          onChange={(e) => setSkuInput(e.target.value)}
          placeholder="SKU001, SKU002, SKU003"
         />
        </div>
        {dataPreview && dataPreview.dataset_type === 'sales' && (
         <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700">
          Using Sales dataset with {dataPreview.rows} rows · {startDate} → {endDate}
         </div>
        )}
        <div className="grid grid-cols-2 gap-3">
         <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">Start Date</label>
          <input
           type="date"
           className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
           value={startDate}
           onChange={(e) => setStartDate(e.target.value)}
          />
         </div>
         <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">End Date</label>
          <input
           type="date"
           className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
           value={endDate}
           onChange={(e) => setEndDate(e.target.value)}
          />
         </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
         <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">Granularity</label>
          <select
           className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
           value={granularity}
           onChange={(e) => setGranularity(e.target.value as any)}
          >
           <option value="D">Daily</option>
           <option value="W">Weekly</option>
           <option value="M">Monthly</option>
          </select>
         </div>
         <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">Location</label>
          <input
           className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
           value={location}
           onChange={(e) => setLocation(e.target.value)}
           placeholder="All"
          />
         </div>
        </div>
        <div>
         <label className="block text-sm font-medium text-slate-900 mb-1">Forecast model</label>
         <select
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          value={forecastModel}
          onChange={(e) => setForecastModel(e.target.value as any)}
         >
          <option value="auto">Auto (best by MAPE)</option>
          <option value="baseline">Baseline</option>
          <option value="arima">ARIMA</option>
          <option value="prophet">Prophet</option>
          <option value="xgboost">XGBoost</option>
         </select>
        </div>
        <button
         disabled={!canCallApi || loading}
         onClick={handleCreateForecast}
         className="btn-primary w-full"
        >
         Generate Forecast
        </button>
       </div>
      </div>

      <div className="card">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">Generate Plan</h3>
       </div>
       <div className="card-body space-y-4">
        <p className="text-sm text-slate-600">
         Maximize service level subject to inventory constraints based on the forecast.
        </p>
        <button
         disabled={!forecast || !canCallApi || loading}
         onClick={handleGeneratePlan}
         className="btn-primary w-full"
        >
         Generate Plan
        </button>
        {forecast && (
         <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <div className="font-medium mb-1">Forecast ID</div>
          <div className="font-mono break-all">{forecast.forecast_id}</div>
         </div>
        )}
        {plan && (
         <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <div className="font-medium mb-1">Plan ID</div>
          <div className="font-mono break-all">{plan.plan_id}</div>
         </div>
        )}
       </div>
      </div>
     </div>

     {forecast && (
      <div className="card">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">Top Risk SKUs</h3>
        <span className="text-xs text-slate-500">
         {forecast.metadata.model_name} v{forecast.metadata.model_version}
        </span>
       </div>
       <div className="card-body">
        <div className="overflow-x-auto">
         <table className="w-full text-sm">
          <thead>
           <tr className="border-b border-slate-200">
            <th className="px-4 py-3 text-left font-semibold text-slate-700">Rank</th>
            <th className="px-4 py-3 text-left font-semibold text-slate-700">SKU</th>
            <th className="px-4 py-3 text-right font-semibold text-slate-700">Total Volume</th>
           </tr>
          </thead>
          <tbody>
           {topSkuTotals.map(([sku, total], idx) => (
            <tr key={sku} className="border-b border-slate-100 hover:bg-slate-50">
             <td className="px-4 py-3 text-slate-600">#{idx + 1}</td>
             <td className="px-4 py-3 font-mono text-slate-900">{sku}</td>
             <td className="px-4 py-3">
              <div className="flex items-center gap-3">
               <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                <div
                 className="h-full bg-gradient-to-r from-blue-500 to-blue-400"
                 style={{ width: `${(total / maxSkuTotal) * 100 || 0}%` }}
                />
               </div>
               <span className="text-right tabular-nums text-slate-900 font-medium w-20">
                {total.toFixed(0)}
               </span>
              </div>
             </td>
            </tr>
           ))}
          </tbody>
         </table>
        </div>
       </div>
      </div>
     )}

     {forecast && (
      <div className="card">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">Demand Forecast Timeline</h3>
        <span className="text-xs text-slate-500">{horizonPeriods} periods</span>
       </div>
       <div className="card-body">
        {chartData.length === 0 ? (
         <p className="text-sm text-slate-500">No forecast points available.</p>
        ) : (
         <div style={{ width: '100%', height: 260 }}>
          <ResponsiveContainer>
           <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <defs>
             <linearGradient id="meanArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
             </linearGradient>
            </defs>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis
             dataKey="label"
             tick={{ fontSize: 11, fill: '#64748b' }}
             tickLine={false}
             axisLine={{ stroke: '#cbd5e1' }}
            />
            <YAxis
             tick={{ fontSize: 11, fill: '#64748b' }}
             tickLine={false}
             axisLine={{ stroke: '#cbd5e1' }}
             domain={[
              Math.max(0, Math.floor(minBandValue * 0.9)),
              Math.ceil(maxBandValue * 1.1),
             ]}
            />
            <Tooltip
             labelFormatter={(value) => `Date ${value}`}
             contentStyle={{ fontSize: 12 }}
            />
            <Area
             type="monotone"
             dataKey="mean"
             stroke="#22c55e"
             fill="url(#meanArea)"
             strokeWidth={2}
            />
            <Line
             type="monotone"
             dataKey="q90"
             stroke="#38bdf8"
             strokeWidth={1}
             dot={false}
             strokeDasharray="4 3"
            />
            <Line
             type="monotone"
             dataKey="q10"
             stroke="#38bdf8"
             strokeWidth={1}
             dot={false}
             strokeDasharray="4 3"
             opacity={0.7}
            />
           </AreaChart>
          </ResponsiveContainer>
         </div>
        )}
        <p className="mt-4 text-xs text-slate-500">
         Mean demand is shown in green. Dashed blue lines show the q10/q90 confidence band.
        </p>
        {chartData.length > 0 && (
         <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-xs border border-slate-200 rounded">
           <thead className="bg-slate-100">
            <tr>
             <th className="px-2 py-1 text-left text-slate-700">Date</th>
             <th className="px-2 py-1 text-right text-slate-700">Mean</th>
             <th className="px-2 py-1 text-right text-slate-700">q10</th>
             <th className="px-2 py-1 text-right text-slate-700">q90</th>
            </tr>
           </thead>
           <tbody>
            {chartData.slice(0, 30).map((row) => (
             <tr key={row.date} className="odd:bg-slate-50 even:bg-slate-100/60">
              <td className="px-2 py-1 text-slate-800">{row.date}</td>
              <td className="px-2 py-1 text-right text-slate-900">{numberFormatter.format(row.mean)}</td>
              <td className="px-2 py-1 text-right text-slate-800">{numberFormatter.format(row.q10)}</td>
              <td className="px-2 py-1 text-right text-slate-800">{numberFormatter.format(row.q90)}</td>
             </tr>
            ))}
           </tbody>
          </table>
          {chartData.length > 30 && (
           <p className="mt-1 text-[10px] text-slate-400">Showing first 30 periods.</p>
          )}
         </div>
        )}
       </div>
      </div>
     )}

     {forecast && forecast.metadata.per_sku_model && (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 shadow-lg shadow-slate-950/30 text-slate-100">
       <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold">Model selection by SKU</h3>
        <span className="text-xs text-slate-400">ARIMA / Prophet / XGBoost / baseline</span>
       </div>
       <div className="overflow-x-auto text-sm">
        <table className="min-w-full border border-slate-800 rounded">
         <thead className="bg-slate-800/80">
          <tr>
           <th className="px-2 py-1 text-left">SKU</th>
           <th className="px-2 py-1 text-left">Chosen model</th>
           <th className="px-2 py-1 text-right">MAPE</th>
           <th className="px-2 py-1 text-right">MAE</th>
          </tr>
         </thead>
         <tbody>
          {Object.entries(forecast.metadata.per_sku_model).map(([sku, model]) => {
           const metrics = skuMetrics[sku] ?? {};
           const mape = metrics.mape;
           const mae = metrics.mae;
           return (
            <tr key={sku} className="odd:bg-slate-900 even:bg-slate-950/60">
             <td className="px-2 py-1 font-mono text-xs">{sku}</td>
             <td className="px-2 py-1 text-xs">
              {model === 'stub' ? 'Baseline model' : model}
             </td>
             <td className="px-2 py-1 text-right text-xs">
              {mape != null && Number.isFinite(mape) ? `${mape.toFixed(1)}%` : '—'}
             </td>
             <td className="px-2 py-1 text-right text-xs">
              {mae != null && Number.isFinite(mae) ? mae.toFixed(1) : '—'}
             </td>
            </tr>
           );
          })}
         </tbody>
        </table>
       </div>
      </div>
     )}

     {plan && (
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 shadow-lg shadow-slate-950/30 text-slate-100">
       <h3 className="font-semibold mb-2">Plan KPIs</h3>
       <div className="overflow-x-auto text-sm">
        <table className="min-w-full border border-slate-800 rounded">
         <thead className="bg-slate-800/80">
          <tr>
           <th className="px-2 py-1 text-left">KPI</th>
           <th className="px-2 py-1 text-right">Value</th>
           <th className="px-2 py-1 text-left">Unit</th>
          </tr>
         </thead>
         <tbody>
          {plan.kpis.map((kpi) => (
           <tr key={kpi.name} className="odd:bg-slate-900 even:bg-slate-950/60">
            <td className="px-2 py-1">{kpi.name}</td>
            <td className="px-2 py-1 text-right">{kpi.value.toFixed(2)}</td>
            <td className="px-2 py-1">{kpi.unit ?? ''}</td>
           </tr>
          ))}
         </tbody>
        </table>
       </div>
      </div>
     )}

     <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="bg-slate-100 border border-slate-200 rounded-xl p-4 shadow-lg shadow-slate-200/30 text-slate-900">
       <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold">Explainability</h3>
        <button
         disabled={!forecast || !canCallApi || loading}
         onClick={handleExplain}
         className="inline-flex items-center justify-center rounded bg-violet-500 px-3 py-1.5 text-xs font-medium text-slate-950 hover:bg-violet-400 disabled:opacity-50"
        >
         Fetch
        </button>
       </div>
       {explain ? (
        <div className="space-y-2 text-sm">
         <div className="overflow-x-auto">
          <table className="min-w-full border border-slate-200 rounded">
           <thead className="bg-slate-200/80">
            <tr>
             <th className="px-2 py-1 text-left text-slate-800">Feature</th>
             <th className="px-2 py-1 text-right text-slate-800">Importance</th>
             <th className="px-2 py-1 text-left text-slate-800">Direction</th>
            </tr>
           </thead>
           <tbody>
            {explain.global_importance.map((f) => (
             <tr key={f.feature} className="odd:bg-slate-100 even:bg-slate-50/60">
              <td className="px-2 py-1 text-slate-900">{f.feature}</td>
              <td className="px-2 py-1 text-right text-slate-800">{(f.importance * 100).toFixed(1)}%</td>
              <td className="px-2 py-1 text-slate-800">{f.direction}</td>
             </tr>
            ))}
           </tbody>
          </table>
         </div>
         {explain.external_summary && (
          <p className="text-xs text-slate-600">
           External signals: {explain.external_summary}
          </p>
         )}
        </div>
       ) : (
        <p className="text-sm text-slate-700">No explanation loaded yet.</p>
       )}
      </div>

      <div className="bg-slate-100 border border-slate-200 rounded-xl p-4 shadow-lg shadow-slate-200/30">
       <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold">Quick scenario</h3>
        <button
         disabled={!forecast || !plan || !canCallApi || loading}
         onClick={handleScenario}
         className="inline-flex items-center justify-center rounded bg-amber-500 px-3 py-1.5 text-xs font-medium text-slate-950 hover:bg-amber-400 disabled:opacity-50"
        >
         Run
        </button>
       </div>
       <label className="block text-sm mb-2 text-slate-900">
        Demand factor: {scenarioDemandFactor.toFixed(2)}
        <input
         type="range"
         min={0.5}
         max={2.0}
         step={0.05}
         value={scenarioDemandFactor}
         onChange={(e) => setScenarioDemandFactor(parseFloat(e.target.value))}
         className="w-full accent-amber-500"
        />
       </label>
       {scenario ? (
        <div className="overflow-x-auto text-sm">
         <table className="min-w-full border border-slate-200 rounded">
          <thead className="bg-slate-200/80">
           <tr>
            <th className="px-2 py-1 text-left text-slate-800">KPI</th>
            <th className="px-2 py-1 text-right text-slate-800">Base</th>
            <th className="px-2 py-1 text-right text-slate-800">Scenario</th>
            <th className="px-2 py-1 text-right text-slate-800">Delta</th>
           </tr>
          </thead>
          <tbody>
           {scenario.kpis.map((kpi) => (
            <tr key={kpi.name} className="odd:bg-slate-100 even:bg-slate-50/60">
             <td className="px-2 py-1 text-slate-900">{kpi.name}</td>
             <td className="px-2 py-1 text-right text-slate-800">{kpi.base.toFixed(1)}</td>
             <td className="px-2 py-1 text-right text-slate-900 font-medium">{kpi.scenario.toFixed(1)}</td>
             <td className="px-2 py-1 text-right text-slate-800">{kpi.delta.toFixed(1)}</td>
            </tr>
           ))}
          </tbody>
         </table>
        </div>
       ) : (
        <p className="text-sm text-slate-600">Run a scenario once a plan exists.</p>
       )}
       {scenario?.narrative && (
        <p className="mt-2 text-xs text-emerald-700">{scenario.narrative}</p>
       )}
      </div>
     </div>
    </div>
   );
  }

  function renderScenarioLab() {
   return (
    <div className="space-y-6">
     <div className="card card-header">
      <div>
       <h1 className="text-2xl font-bold text-slate-900">Scenario Lab</h1>
       <p className="text-sm text-slate-500 mt-1">
        Explore and compare scenarios to stress-test your supply plan
       </p>
      </div>
     </div>

     <div className="flex items-center gap-3">
      <button
       disabled={!forecast || !plan || !canCallApi || loading}
       onClick={async () => {
        if (!forecast || !plan) return;
        setError(null);
        setDataLoading(true);
        try {
         const params = new URLSearchParams();
         params.set('forecast_id', forecast.forecast_id);
         params.set('plan_id', plan.plan_id);
         const data = await apiRequest<ScenarioListResponse>(
          `/api/v1/scenario?${params.toString()}`,
          {},
          apiBaseUrl,
          apiKey,
         );
         setScenarioList(data.scenarios);
        } catch (e: any) {
         setError(e.message ?? String(e));
        } finally {
         setDataLoading(false);
        }
       }}
       className="btn-primary"
      >
       Refresh Scenarios
      </button>
      {!forecast || !plan ? (
       <span className="text-sm text-slate-500">
        Generate a forecast and plan on the Control Tower tab first.
       </span>
      ) : (
       <span className="text-sm text-slate-600">
        Forecast: <span className="font-mono text-xs">{forecast.forecast_id.slice(0, 8)}</span> | Plan: <span className="font-mono text-xs">{plan.plan_id.slice(0, 8)}</span>
       </span>
      )}
     </div>

     <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="card md:col-span-1">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">Scenarios</h3>
        {dataLoading && <span className="text-xs text-slate-500">Loading...</span>}
       </div>
       <div className="card-body">
        {scenarioList.length === 0 ? (
         <p className="text-sm text-slate-500">No scenarios yet. Run a scenario on the dashboard first.</p>
        ) : (
         <div className="space-y-2">
          {scenarioList.map((s) => (
           <div
            key={s.scenario_id}
            onClick={() => fetchScenarioDetails(s.scenario_id)}
            className={`p-3 rounded-lg border cursor-pointer transition-all ${
             selectedScenarioId === s.scenario_id
              ? 'border-blue-500 bg-blue-50'
              : 'border-slate-200 bg-white hover:border-slate-300'
            }`}
           >
            <div className="font-medium text-slate-900">{s.name ?? 'Unnamed'}</div>
            <div className="text-xs text-slate-500 font-mono mt-1">{s.scenario_id.slice(0, 12)}...</div>
           </div>
          ))}
         </div>
        )}
       </div>
      </div>

      <div className="card md:col-span-2">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">Scenario Details</h3>
        {scenarioDetailLoading && <span className="text-xs text-slate-500">Loading...</span>}
       </div>
       <div className="card-body">
        {!selectedScenario ? (
         <p className="text-sm text-slate-500">Select a scenario to view details and KPI impact.</p>
        ) : (
         <div className="space-y-4">
          <div>
           <div className="text-lg font-semibold text-slate-900">{selectedScenario.name ?? 'Unnamed Scenario'}</div>
           <div className="text-xs text-slate-500 mt-2 space-y-1">
            <div>Scenario ID: <span className="font-mono">{selectedScenario.scenario_id.slice(0, 16)}...</span></div>
            <div>Forecast ID: <span className="font-mono">{selectedScenario.forecast_id.slice(0, 16)}...</span></div>
            {selectedScenario.plan_id && (
             <div>Plan ID: <span className="font-mono">{selectedScenario.plan_id.slice(0, 16)}...</span></div>
            )}
           </div>
          </div>

          {selectedScenario.narrative && (
           <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
            <div className="text-sm font-medium text-emerald-900 mb-1">Scenario Narrative</div>
            <div className="text-sm text-emerald-800">{selectedScenario.narrative}</div>
           </div>
          )}

          <div>
           <div className="font-semibold text-slate-900 mb-3">KPI Impact</div>
           <div className="overflow-x-auto">
            <table className="w-full text-sm">
             <thead>
              <tr className="border-b border-slate-200">
               <th className="px-3 py-2 text-left font-semibold text-slate-700">KPI</th>
               <th className="px-3 py-2 text-right font-semibold text-slate-700">Base</th>
               <th className="px-3 py-2 text-right font-semibold text-slate-700">Scenario</th>
               <th className="px-3 py-2 text-right font-semibold text-slate-700">Delta</th>
              </tr>
             </thead>
             <tbody>
              {selectedScenario.kpis.map((kpi) => (
               <tr key={kpi.name} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-3 py-2 text-slate-900">{kpi.name}</td>
                <td className="px-3 py-2 text-right text-slate-600">{kpi.base.toFixed(1)}</td>
                <td className="px-3 py-2 text-right text-slate-900 font-medium">{kpi.scenario.toFixed(1)}</td>
                <td className={`px-3 py-2 text-right font-medium ${kpi.delta >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                 {kpi.delta >= 0 ? '+' : ''}{kpi.delta.toFixed(1)}
                </td>
               </tr>
              ))}
             </tbody>
            </table>
           </div>
          </div>
         </div>
        )}
       </div>
      </div>
     </div>
    </div>
   );
  }

  function renderDataImport() {
   return (
    <div className="space-y-6">
     <div className="card card-header">
      <div>
       <h1 className="text-2xl font-bold text-slate-900">Data Import</h1>
       <p className="text-sm text-slate-500 mt-1">
        Upload and manage planning datasets for forecasting and supply planning
       </p>
      </div>
     </div>

     <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="card">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">1. Select Dataset</h3>
       </div>
       <div className="card-body space-y-4">
        <div>
         <label className="block text-sm font-medium text-slate-900 mb-2">Dataset Type</label>
         <select
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          value={datasetType}
          onChange={(e) => setDatasetType(e.target.value as DatasetType)}
         >
          {Object.entries(DATASET_LABELS).map(([type, label]) => (
           <option key={type} value={type}>
            {label}
           </option>
          ))}
         </select>
        </div>
        <button
         disabled={!canCallApi || dataLoading}
         onClick={async () => {
          setError(null);
          setDataLoading(true);
          try {
           const params = new URLSearchParams();
           params.set('dataset_type', datasetType);
           params.set('limit', '20');
           const data = await apiRequest<DatasetPreview>(
            `/api/v1/data/preview?${params.toString()}`,
            {},
            apiBaseUrl,
            apiKey,
           );
           setDataPreview(data);
           const guessed = guessDatasetTypeFromColumns(data.columns);
           if (guessed && guessed !== datasetType) {
            setDatasetType(guessed);
           }
           if ((guessed ?? data.dataset_type) === 'sales') {
            maybeAdoptSalesDefaults(data);
           }
          } catch (e: any) {
           setError(e.message ?? String(e));
          } finally {
           setDataLoading(false);
          }
         }}
         className="btn-primary w-full"
        >
         Preview Dataset
        </button>
       </div>
      </div>

      <div className="card">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">2. Upload file</h3>
       </div>
       <div className="card-body space-y-4">
        <p className="text-sm text-slate-600">
         Upload a CSV or Excel file to replace the sample data for the selected dataset type.
        </p>
        <div>
         <label className="block text-sm font-medium text-slate-700 mb-2">Select File</label>
         <input
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={(e) => {
           const file = e.target.files?.[0] ?? null;
           setSelectedFile(file);
           if (file) {
            const guess = guessDatasetTypeFromFileName(file.name);
            if (guess && guess !== datasetType) {
             setDatasetType(guess);
            }
           }
          }}
          className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
         />
        </div>
        {selectedFile && (
         <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">
          Selected: <span className="font-medium">{selectedFile.name}</span>
         </div>
        )}
        <button
         disabled={!canCallApi || !selectedFile || uploading}
         onClick={async () => {
          if (!selectedFile) return;
          setError(null);
          setUploading(true);
          try {
           const form = new FormData();
           form.append('dataset_type', datasetType);
           form.append('file', selectedFile);
           const data = await apiUpload<DatasetPreview>(
            '/api/v1/data/upload',
            form,
            apiBaseUrl,
            apiKey,
           );
           setDataPreview(data);
           const guessed = guessDatasetTypeFromColumns(data.columns);
           if (guessed && guessed !== datasetType) {
            setDatasetType(guessed);
           }
           if ((guessed ?? data.dataset_type) === 'sales') {
            maybeAdoptSalesDefaults(data);
           }
          } catch (e: any) {
           setError(e.message ?? String(e));
          } finally {
           setUploading(false);
          }
         }}
         className="btn-primary w-full"
        >
         Upload CSV
        </button>
       </div>
      </div>
     </div>

     {dataPreview && (
      <div className="card">
       <div className="card-header">
        <h3 className="font-semibold text-slate-900">Data Preview</h3>
        <span className="text-xs text-slate-500">
         {dataPreview.rows} rows · {dataPreview.columns.length} columns
        </span>
       </div>
       <div className="card-body space-y-4">
        {dataPreview.warnings && dataPreview.warnings.length > 0 && (
         <div className="space-y-2">
          {dataPreview.warnings.map((w, idx) => (
           <div key={idx} className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
            ⚠️ {w}
           </div>
          ))}
         </div>
        )}
        <div className="overflow-x-auto">
         <table className="w-full text-sm">
          <thead>
           <tr className="border-b border-slate-200">
            {dataPreview.columns.map((col) => (
             <th key={col} className="px-4 py-3 text-left font-semibold text-slate-700">
              {col}
             </th>
            ))}
           </tr>
          </thead>
          <tbody>
           {(dataPreview.preview ?? []).map((row, idx) => (
            <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
             {dataPreview.columns.map((col) => (
              <td key={col} className="px-4 py-3 text-slate-900">
               {String((row as any)[col] ?? '—')}
              </td>
             ))}
            </tr>
           ))}
          </tbody>
         </table>
        </div>
       </div>
      </div>
     )}
    </div>
   );
  }

  return (
   <div className="min-h-screen flex flex-col bg-white">
    <header className="border-b border-slate-200 bg-white shadow-sm sticky top-0 z-40">
     <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
       <div className="h-10 w-10 rounded-lg bg-blue-600 text-white font-bold text-lg flex items-center justify-center">
        I
       </div>
       <div>
        <div className="text-lg font-bold text-slate-900">IBP Control Tower</div>
        <div className="text-xs text-slate-500">Integrated Business Planning Platform</div>
       </div>
      </div>
      <nav className="flex items-center gap-1">
       {NAV_ITEMS.map((item) => {
        const isActive = page === item.id;
        return (
         <button
          key={item.id}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
           isActive
            ? 'bg-blue-600 text-white shadow-sm'
            : 'text-slate-600 hover:bg-slate-100'
          }`}
          onClick={() => setPage(item.id)}
         >
          {item.label}
         </button>
        );
       })}
      </nav>
     </div>
    </header>

    <main className="flex-1 bg-slate-50">
     <div className="mx-auto max-w-7xl px-6 py-8 flex gap-8">
      <div className="flex-1">
       {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
         <div className="font-semibold">Error</div>
         <div>{error}</div>
        </div>
       )}
       {loading && (
        <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
         <div className="font-semibold">Processing...</div>
         <div>Running operation, please wait.</div>
        </div>
       )}

       {page === 'dashboard' && renderDashboard()}
       {page === 'scenario' && renderScenarioLab()}
       {page === 'data' && renderDataImport()}
      </div>

      <aside className="w-96 shrink-0">
       <div className="sticky top-24 card space-y-4 px-4 py-4">
        <div className="card-header">
         <div>
          <div className="text-lg font-bold text-slate-900">AI Copilot</div>
          <div className="text-xs text-slate-500 mt-1">Intelligent Planning Assistant</div>
         </div>
         <span className="badge badge-success">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          Live
         </span>
        </div>

        <div>
         <div className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-3">Context</div>
         <div className="flex flex-wrap gap-2">
          <label className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer transition-all font-medium text-sm ${
           copilotContextForecast
            ? 'border-blue-500 bg-blue-50 text-blue-700'
            : 'border-slate-300 bg-white text-slate-700 hover:border-blue-300'
          }`}>
           <input
            type="checkbox"
            checked={copilotContextForecast}
            onChange={(e) => setCopilotContextForecast(e.target.checked)}
            className="rounded"
           />
           Forecast
          </label>
          <label className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer transition-all font-medium text-sm ${
           copilotContextPlan
            ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
            : 'border-slate-300 bg-white text-slate-700 hover:border-emerald-300'
          }`}>
           <input
            type="checkbox"
            checked={copilotContextPlan}
            onChange={(e) => setCopilotContextPlan(e.target.checked)}
            className="rounded"
           />
           Plan
          </label>
          <label className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer transition-all font-medium text-sm ${
           copilotContextScenario
            ? 'border-amber-500 bg-amber-50 text-amber-700'
            : 'border-slate-300 bg-white text-slate-700 hover:border-amber-300'
          }`}>
           <input
            type="checkbox"
            checked={copilotContextScenario}
            onChange={(e) => setCopilotContextScenario(e.target.checked)}
            className="rounded"
           />
           Scenarios
          </label>
          <label className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer transition-all font-medium text-sm ${
           copilotContextData
            ? 'border-purple-500 bg-purple-50 text-purple-700'
            : 'border-slate-300 bg-white text-slate-700 hover:border-purple-300'
          }`}>
           <input
            type="checkbox"
            checked={copilotContextData}
            onChange={(e) => setCopilotContextData(e.target.checked)}
            className="rounded"
           />
           Data
          </label>
         </div>
        </div>

        <div className="rounded-xl border border-blue-200 bg-blue-50 p-3">
         <textarea
          className="w-full rounded-lg border border-blue-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500/30 resize-none h-24 font-medium"
          placeholder="Ask me anything: risks, KPIs, data quality, scenarios..."
          value={copilotInput}
          onChange={(e) => setCopilotInput(e.target.value)}
         />
         <button
          disabled={!canCallApi || copilotLoading || !copilotInput.trim()}
          onClick={handleCopilotAsk}
          className="mt-3 btn-primary w-full"
         >
          {copilotLoading ? '⏳ Analyzing...' : '🚀 Ask Copilot'}
         </button>
        </div>

        {copilotMessages.length > 0 ? (
         <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
          {copilotMessages.map((m, idx) => (
           <div
            key={idx}
            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
           >
            <div
             className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
              m.role === 'user'
               ? 'bg-blue-600 text-white shadow-md'
               : 'bg-slate-100 border border-slate-200 text-slate-900 shadow-sm'
             }`}
            >
             <div className={`text-xs font-semibold mb-1 ${m.role === 'user' ? 'text-blue-100' : 'text-slate-500'}`}>
              {m.role === 'user' ? '👤 You' : '🤖 Copilot'}
             </div>
             <div className="whitespace-pre-wrap">{m.text}</div>
            </div>
           </div>
          ))}
         </div>
        ) : (
         <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
          <div className="font-semibold mb-2">💡 Try asking:</div>
          <ul className="space-y-1 text-xs">
           <li>• What are the top demand risks?</li>
           <li>• How's the plan health?</li>
           <li>• Compare scenarios</li>
           <li>• Data quality check</li>
          </ul>
         </div>
        )}
        {copilotActions.length > 0 && (
         <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-700 space-y-1">
          <div className="font-semibold text-slate-900">Suggested next steps</div>
          <ul className="list-disc pl-4 space-y-0.5">
           {copilotActions.map((a, idx) => (
            <li key={idx}>{a}</li>
           ))}
          </ul>
         </div>
        )}
       </div>
      </aside>
     </div>
    </main>

    <footer className="border-t border-slate-200 bg-white text-[11px] text-slate-500">
     <div className="mx-auto max-w-6xl px-4 py-2 flex items-center justify-between">
      <span>IBP AI Platform · Prototype</span>
      <span>Backend: FastAPI · Frontend: React + Vite + Tailwind</span>
     </div>
    </footer>
   </div>
  );
 }

export default App;
