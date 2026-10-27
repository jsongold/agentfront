"use client";

import { JsonEditor } from "@/components/json-editor";
import { SchemaForm } from "@/components/schema-form";
import { CONVERSION_TYPES } from "@/lib/labels";
import type { AdapterInfo, Catalog, ConversionPointDraft, Offering, Work } from "@/lib/types";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Card, Col, Collapse, Form, Input, InputNumber, Row, Select, Space, Switch, Typography } from "antd";

const KINDS = [
  { value: "service", label: "サービス" },
  { value: "product", label: "商品" },
  { value: "creative_work", label: "実績・作品" },
];

function offeringSchema(document: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!document) return null;
  const defs = (document.$defs || document.definitions) as Record<string, unknown> | undefined;
  const nested = defs?.offering;
  return nested && typeof nested === "object" ? (nested as Record<string, unknown>) : null;
}

function Tags({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
}) {
  return (
    <Select
      mode="tags"
      style={{ width: "100%" }}
      value={value}
      placeholder={placeholder}
      tokenSeparators={["、", ","]}
      onChange={onChange}
    />
  );
}

export function CatalogEditor({
  catalog,
  revision,
  schemaDocument,
  adapters,
  jsonError,
  onChange,
  onJsonError,
}: {
  catalog: Catalog;
  revision: string;
  schemaDocument: Record<string, unknown> | null;
  adapters: AdapterInfo[];
  jsonError: string | null;
  onChange: (catalog: Catalog) => void;
  onJsonError: (key: string, message: string | null) => void;
}) {
  function patch(partial: Partial<Catalog>) {
    onChange({ ...catalog, ...partial });
  }

  function patchOffering(index: number, partial: Partial<Offering>) {
    patch({
      offerings: catalog.offerings.map((item, i) => (i === index ? { ...item, ...partial } : item)),
    });
  }

  function patchWork(index: number, partial: Partial<Work>) {
    patch({ works: catalog.works.map((item, i) => (i === index ? { ...item, ...partial } : item)) });
  }

  function patchPoint(index: number, partial: Partial<ConversionPointDraft>) {
    patch({
      conversion_points: catalog.conversion_points.map((item, i) => (i === index ? { ...item, ...partial } : item)),
    });
  }

  const nested = offeringSchema(schemaDocument);
  const price = catalog.price_range;

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <Card title="基本情報" size="small">
        <Form layout="vertical">
          <Row gutter={12}>
            <Col xs={24} md={12}>
              <Form.Item label="名称">
                <Input value={catalog.name} onChange={(event) => patch({ name: event.target.value })} />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="スラッグ" extra="公開URLに使います。英小文字とハイフン。">
                <Input value={catalog.slug} onChange={(event) => patch({ slug: event.target.value })} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="要約">
            <Input.TextArea rows={2} value={catalog.summary} onChange={(event) => patch({ summary: event.target.value })} />
          </Form.Item>
          <Form.Item label="説明">
            <Input.TextArea rows={4} value={catalog.description} onChange={(event) => patch({ description: event.target.value })} />
          </Form.Item>
          <Row gutter={12}>
            <Col xs={24} md={12}>
              <Form.Item label="対応エリア">
                <Tags value={catalog.service_area} onChange={(service_area) => patch({ service_area })} placeholder="鎌倉" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="タグ">
                <Tags value={catalog.tags} onChange={(tags) => patch({ tags })} placeholder="木造" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="schema.org の型">
            <Input value={catalog.schema_org_type} onChange={(event) => patch({ schema_org_type: event.target.value })} />
          </Form.Item>
        </Form>
      </Card>

      <Card title="売り手" size="small">
        <Form layout="vertical">
          <Row gutter={12}>
            <Col xs={24} md={12}>
              <Form.Item label="名称">
                <Input
                  value={catalog.seller.name}
                  onChange={(event) => patch({ seller: { ...catalog.seller, name: event.target.value } })}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="正式名称">
                <Input
                  value={catalog.seller.legal_name || ""}
                  onChange={(event) => patch({ seller: { ...catalog.seller, legal_name: event.target.value || null } })}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="メール">
                <Input
                  value={catalog.seller.email || ""}
                  onChange={(event) => patch({ seller: { ...catalog.seller, email: event.target.value || null } })}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="電話">
                <Input
                  value={catalog.seller.phone || ""}
                  onChange={(event) => patch({ seller: { ...catalog.seller, phone: event.target.value || null } })}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="住所">
            <Input
              value={catalog.seller.address || ""}
              onChange={(event) => patch({ seller: { ...catalog.seller, address: event.target.value || null } })}
            />
          </Form.Item>
        </Form>
      </Card>

      <Card title="価格帯と信頼情報" size="small">
        <Form layout="vertical">
          <Row gutter={12}>
            <Col xs={12} md={6}>
              <Form.Item label="下限">
                <InputNumber
                  style={{ width: "100%" }}
                  value={price?.min_amount ?? null}
                  onChange={(value) =>
                    patch({
                      price_range: {
                        min_amount: value ?? null,
                        max_amount: price?.max_amount ?? null,
                        currency: price?.currency || "JPY",
                        unit: price?.unit,
                        note: price?.note,
                      },
                    })
                  }
                />
              </Form.Item>
            </Col>
            <Col xs={12} md={6}>
              <Form.Item label="上限">
                <InputNumber
                  style={{ width: "100%" }}
                  value={price?.max_amount ?? null}
                  onChange={(value) =>
                    patch({
                      price_range: {
                        min_amount: price?.min_amount ?? null,
                        max_amount: value ?? null,
                        currency: price?.currency || "JPY",
                        unit: price?.unit,
                        note: price?.note,
                      },
                    })
                  }
                />
              </Form.Item>
            </Col>
            <Col xs={12} md={6}>
              <Form.Item label="通貨">
                <Input
                  value={price?.currency || "JPY"}
                  onChange={(event) =>
                    patch({
                      price_range: {
                        min_amount: price?.min_amount ?? null,
                        max_amount: price?.max_amount ?? null,
                        currency: event.target.value || "JPY",
                        unit: price?.unit,
                        note: price?.note,
                      },
                    })
                  }
                />
              </Form.Item>
            </Col>
            <Col xs={12} md={6}>
              <Form.Item label="単位">
                <Input
                  value={price?.unit || ""}
                  onChange={(event) =>
                    patch({
                      price_range: {
                        min_amount: price?.min_amount ?? null,
                        max_amount: price?.max_amount ?? null,
                        currency: price?.currency || "JPY",
                        unit: event.target.value || null,
                        note: price?.note,
                      },
                    })
                  }
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="価格の注記">
            <Input
              value={price?.note || ""}
              onChange={(event) =>
                patch({
                  price_range: {
                    min_amount: price?.min_amount ?? null,
                    max_amount: price?.max_amount ?? null,
                    currency: price?.currency || "JPY",
                    unit: price?.unit,
                    note: event.target.value || null,
                  },
                })
              }
            />
          </Form.Item>
          <Row gutter={12}>
            <Col xs={24} md={8}>
              <Form.Item label="許認可">
                <Tags
                  value={catalog.trust.licenses}
                  onChange={(licenses) => patch({ trust: { ...catalog.trust, licenses } })}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="資格・認証">
                <Tags
                  value={catalog.trust.certifications}
                  onChange={(certifications) => patch({ trust: { ...catalog.trust, certifications } })}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="業歴（年）">
                <InputNumber
                  style={{ width: "100%" }}
                  value={catalog.trust.years_in_business}
                  onChange={(years_in_business) => patch({ trust: { ...catalog.trust, years_in_business } })}
                />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Card>

      <Card title="業種ごとの追加項目" size="small">
        <Typography.Paragraph type="secondary">
          左のスキーマに沿って入力します。項目を増やすときはスキーマ側にプロパティを足してください。コアの項目はここには出ません。
        </Typography.Paragraph>
        <SchemaForm schema={schemaDocument} formData={catalog.extension} onChange={(extension) => patch({ extension: extension as Record<string, unknown> })} />
      </Card>

      <Card
        title="提供内容"
        size="small"
        extra={
          <Button
            size="small"
            icon={<PlusOutlined />}
            onClick={() =>
              patch({
                offerings: [
                  ...catalog.offerings,
                  {
                    name: "新しい提供",
                    slug: "",
                    kind: "service",
                    description: "",
                    price_range: null,
                    tags: [],
                    area: [],
                    images: [],
                    schema_org_type: "Service",
                    extension: {},
                  },
                ],
              })
            }
          >
            追加
          </Button>
        }
      >
        <Collapse
          items={catalog.offerings.map((offering, index) => ({
            key: String(index),
            label: offering.name || `提供 ${index + 1}`,
            children: (
              <Form layout="vertical">
                <Row gutter={12}>
                  <Col xs={24} md={12}>
                    <Form.Item label="名称">
                      <Input value={offering.name} onChange={(event) => patchOffering(index, { name: event.target.value })} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item label="スラッグ">
                      <Input value={offering.slug} onChange={(event) => patchOffering(index, { slug: event.target.value })} />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item label="種別">
                  <Select
                    value={offering.kind}
                    options={KINDS}
                    onChange={(kind) =>
                      patchOffering(index, {
                        kind,
                        schema_org_type: kind === "product" ? "Product" : kind === "creative_work" ? "CreativeWork" : "Service",
                      })
                    }
                  />
                </Form.Item>
                <Form.Item label="説明">
                  <Input.TextArea rows={3} value={offering.description} onChange={(event) => patchOffering(index, { description: event.target.value })} />
                </Form.Item>
                <Form.Item label="タグ">
                  <Tags value={offering.tags} onChange={(tags) => patchOffering(index, { tags })} />
                </Form.Item>
                {nested ? (
                  <SchemaForm
                    schema={nested}
                    formData={offering.extension}
                    onChange={(extension) => patchOffering(index, { extension: extension as Record<string, unknown> })}
                  />
                ) : null}
                <Button danger icon={<MinusCircleOutlined />} onClick={() => patch({ offerings: catalog.offerings.filter((_, i) => i !== index) })}>
                  この提供を外す
                </Button>
              </Form>
            ),
          }))}
        />
      </Card>

      <Card
        title="実績"
        size="small"
        extra={
          <Button
            size="small"
            icon={<PlusOutlined />}
            onClick={() =>
              patch({
                works: [
                  ...catalog.works,
                  {
                    title: "新しい実績",
                    slug: "",
                    description: "",
                    year: null,
                    client: null,
                    location: null,
                    url: null,
                    images: [],
                    schema_org_type: "CreativeWork",
                    extension: {},
                  },
                ],
              })
            }
          >
            追加
          </Button>
        }
      >
        <Collapse
          items={catalog.works.map((work, index) => ({
            key: String(index),
            label: work.title || `実績 ${index + 1}`,
            children: (
              <Form layout="vertical">
                <Form.Item label="題名">
                  <Input value={work.title} onChange={(event) => patchWork(index, { title: event.target.value })} />
                </Form.Item>
                <Form.Item label="説明">
                  <Input.TextArea rows={3} value={work.description} onChange={(event) => patchWork(index, { description: event.target.value })} />
                </Form.Item>
                <Row gutter={12}>
                  <Col xs={24} md={8}>
                    <Form.Item label="年">
                      <InputNumber style={{ width: "100%" }} value={work.year} onChange={(year) => patchWork(index, { year })} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item label="依頼者">
                      <Input value={work.client || ""} onChange={(event) => patchWork(index, { client: event.target.value || null })} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item label="場所">
                      <Input value={work.location || ""} onChange={(event) => patchWork(index, { location: event.target.value || null })} />
                    </Form.Item>
                  </Col>
                </Row>
                <Button danger onClick={() => patch({ works: catalog.works.filter((_, i) => i !== index) })}>
                  この実績を外す
                </Button>
              </Form>
            ),
          }))}
        />
      </Card>

      <Card
        title="コンバージョン地点"
        size="small"
        extra={
          <Button
            size="small"
            icon={<PlusOutlined />}
            onClick={() =>
              patch({
                conversion_points: [
                  ...catalog.conversion_points,
                  {
                    key: "",
                    type: "inquiry",
                    name: "問い合わせ",
                    description: "",
                    input_schema: {
                      type: "object",
                      additionalProperties: false,
                      properties: { message: { type: "string", title: "内容" } },
                      required: ["message"],
                    },
                    external_url: null,
                    offering_slug: null,
                    adapters: [{ key: "internal", config: {} }],
                    enabled: true,
                  },
                ],
              })
            }
          >
            追加
          </Button>
        }
      >
        <Collapse
          items={catalog.conversion_points.map((point, index) => ({
            key: String(index),
            label: `${point.name || "地点"}（${CONVERSION_TYPES.find((item) => item.value === point.type)?.label || point.type}）`,
            children: (
              <Form layout="vertical">
                <Row gutter={12}>
                  <Col xs={24} md={12}>
                    <Form.Item label="表示名">
                      <Input value={point.name} onChange={(event) => patchPoint(index, { name: event.target.value })} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={12}>
                    <Form.Item label="種別">
                      <Select options={CONVERSION_TYPES} value={point.type} onChange={(type) => patchPoint(index, { type })} />
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item label="説明">
                  <Input.TextArea rows={2} value={point.description} onChange={(event) => patchPoint(index, { description: event.target.value })} />
                </Form.Item>
                <Form.Item label="有効">
                  <Switch checked={point.enabled} onChange={(enabled) => patchPoint(index, { enabled })} />
                </Form.Item>
                {point.type === "external_link" ? (
                  <Form.Item label="外部URL">
                    <Input value={point.external_url || ""} onChange={(event) => patchPoint(index, { external_url: event.target.value || null })} />
                  </Form.Item>
                ) : null}
                <Form.Item label="入力スキーマ" extra="エージェントが submit_conversion に渡す項目です。">
                  <JsonEditor
                    resetKey={`${revision}-point-${index}`}
                    value={point.input_schema}
                    rows={8}
                    onChange={(value, error) => {
                      onJsonError(`point-${index}`, error);
                      if (!error && value && typeof value === "object") {
                        patchPoint(index, { input_schema: value as Record<string, unknown> });
                      }
                    }}
                  />
                </Form.Item>
                <Form.Item label="送信先アダプタ" extra="選んだアダプタへ同じ依頼を送ります。未選択のときは保存時に内部記録だけ残します。">
                  <Select
                    mode="multiple"
                    style={{ width: "100%" }}
                    value={point.adapters.map((item) => item.key)}
                    options={adapters.map((item) => ({ value: item.key, label: item.title }))}
                    onChange={(keys: string[]) => {
                      const next = keys.map((key) => point.adapters.find((item) => item.key === key) || { key, config: {} });
                      patchPoint(index, { adapters: next });
                    }}
                  />
                </Form.Item>
                {point.adapters.map((binding) => {
                  const info = adapters.find((item) => item.key === binding.key);
                  if (!info || !Object.keys((info.config_schema.properties as object) || {}).length) return null;
                  return (
                    <div key={binding.key}>
                      <Typography.Text strong>{info.title}</Typography.Text>
                      <SchemaForm
                        schema={info.config_schema}
                        formData={binding.config}
                        onChange={(config) =>
                          patchPoint(index, {
                            adapters: point.adapters.map((item) =>
                              item.key === binding.key ? { ...item, config: (config || {}) as Record<string, unknown> } : item,
                            ),
                          })
                        }
                      />
                    </div>
                  );
                })}
                <Button danger onClick={() => patch({ conversion_points: catalog.conversion_points.filter((_, i) => i !== index) })}>
                  この地点を外す
                </Button>
              </Form>
            ),
          }))}
        />
        {jsonError ? <Typography.Text type="danger">{jsonError}</Typography.Text> : null}
      </Card>

      {catalog.images.length ? (
        <Card title="画像" size="small">
          {catalog.images.map((image) => (
            <div key={image.url}>
              <Typography.Link href={image.url} target="_blank">
                {image.alt || image.url}
              </Typography.Link>
            </div>
          ))}
        </Card>
      ) : null}
    </Space>
  );
}
