export const STATUS: Record<string, { color: string; label: string }> = {
  draft: { color: "default", label: "下書き" },
  queued: { color: "processing", label: "待機中" },
  crawling: { color: "processing", label: "ページ取得中" },
  generating: { color: "processing", label: "生成中" },
  review: { color: "blue", label: "レビュー待ち" },
  published: { color: "green", label: "公開中" },
  failed: { color: "red", label: "失敗" },
  running: { color: "processing", label: "実行中" },
  dispatched: { color: "green", label: "送信済み" },
  partial_failure: { color: "orange", label: "一部失敗" },
  recorded: { color: "blue", label: "記録のみ" },
};

export const CONVERSION_TYPES: { value: string; label: string }[] = [
  { value: "purchase", label: "購入意向" },
  { value: "quote_request", label: "見積依頼" },
  { value: "inquiry", label: "問い合わせ" },
  { value: "booking", label: "予約" },
  { value: "document_request", label: "資料請求" },
  { value: "external_link", label: "外部リンク" },
];

export function statusOf(value: string | undefined) {
  if (!value) return { color: "default", label: "不明" };
  return STATUS[value] ?? { color: "default", label: value };
}

export function typeLabel(value: string | undefined) {
  return CONVERSION_TYPES.find((item) => item.value === value)?.label ?? value ?? "";
}
