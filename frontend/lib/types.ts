export type PriceRange = {
  min_amount: number | null;
  max_amount: number | null;
  currency: string;
  unit?: string | null;
  note?: string | null;
};

export type Media = { url: string; alt?: string | null; kind?: string };

export type Seller = {
  name: string;
  legal_name?: string | null;
  url?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
};

export type TrustInfo = {
  licenses: string[];
  years_in_business: number | null;
  certifications: string[];
  awards: string[];
  insurance: string | null;
};

export type AdapterBinding = { key: string; config: Record<string, unknown> };

export type Offering = {
  name: string;
  slug: string;
  kind: string;
  description: string;
  price_range: PriceRange | null;
  tags: string[];
  area: string[];
  images: Media[];
  schema_org_type: string;
  extension: Record<string, unknown>;
};

export type Work = {
  title: string;
  slug: string;
  description: string;
  year: number | null;
  client: string | null;
  location: string | null;
  url: string | null;
  images: Media[];
  schema_org_type: string;
  extension: Record<string, unknown>;
};

export type ConversionPointDraft = {
  key: string;
  type: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  external_url: string | null;
  offering_slug: string | null;
  adapters: AdapterBinding[];
  enabled: boolean;
};

export type Catalog = {
  name: string;
  slug: string;
  summary: string;
  description: string;
  seller: Seller;
  service_area: string[];
  tags: string[];
  price_range: PriceRange | null;
  trust: TrustInfo;
  schema_org_type: string;
  images: Media[];
  offerings: Offering[];
  works: Work[];
  conversion_points: ConversionPointDraft[];
  extension: Record<string, unknown>;
  source_urls: string[];
  source_description: string;
  vertical_key: string | null;
};

export type RunBrief = {
  id: string;
  status: string;
  step: string | null;
  error: string | null;
  model: string | null;
  created_at: string | null;
  finished_at: string | null;
};

export type BusinessRow = {
  id: string;
  name: string;
  slug: string;
  status: string;
  summary: string;
  description: string;
  service_area: string[];
  tags: string[];
  vertical_key: string | null;
  schema_org_type: string;
  source_urls: string[];
  source_description: string;
  last_error: string | null;
  offering_count: number;
  work_count: number;
  conversion_point_count: number;
  public_url: string | null;
  markdown_url: string | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  latest_run: RunBrief | null;
};

export type VerticalSchemaView = {
  id: string;
  key: string;
  version: number;
  title: string;
  description: string;
  json_schema: Record<string, unknown>;
};

export type SourceDoc = {
  url: string;
  ok: boolean;
  title: string | null;
  text: string | null;
  metadata: Record<string, unknown> | null;
  error: string | null;
};

export type ReviewPayload = {
  business: BusinessRow;
  run: RunBrief | null;
  sources: SourceDoc[];
  vertical_schema: VerticalSchemaView | null;
  catalog: Catalog | null;
};

export type AdapterInfo = {
  key: string;
  title: string;
  config_schema: Record<string, unknown>;
};

export type ConversionPointRow = {
  id: string;
  business_id: string;
  business_name: string;
  business_slug: string;
  key: string;
  type: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  external_url: string | null;
  enabled: boolean;
  adapters: AdapterBinding[];
};

export type DeliveryRow = {
  id: string;
  adapter_key: string;
  status: string;
  detail: string | null;
  created_at: string;
};

export type ConversionRow = {
  id: string;
  business_id: string;
  business_name: string;
  conversion_point_id: string;
  conversion_name: string;
  conversion_type: string;
  payload: Record<string, unknown>;
  agent_name: string | null;
  agent_class: string | null;
  request_text: string | null;
  status: string;
  created_at: string;
  deliveries?: DeliveryRow[];
};

export type AnalyticsSummary = {
  days: number;
  businesses_published: number;
  totals: { mcp_calls: number; page_fetches: number; conversions: number };
  mcp_calls: { day: string; label: string; count: number }[];
  page_fetches: { day: string; label: string; count: number }[];
  conversions: { day: string; label: string; count: number }[];
  recent_conversions: ConversionRow[];
};

export type MetaInfo = {
  public_base_url: string;
  mcp_url: string;
  llm_configured: boolean;
  llm_model: string;
  llm_api_base?: string;
  llm_env: string;
  llm_hint: string;
  mailpit_url: string;
};

export const BUSY = new Set(["queued", "running", "crawling", "generating"]);
