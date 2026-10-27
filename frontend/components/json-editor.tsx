"use client";

import { Input } from "antd";
import { useEffect, useState } from "react";

export function JsonEditor({
  resetKey,
  value,
  onChange,
  rows = 10,
}: {
  resetKey: string;
  value: unknown;
  onChange: (value: unknown, error: string | null) => void;
  rows?: number;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText(JSON.stringify(value ?? {}, null, 2));
    setError(null);
    // Reload only when the surrounding record changes, not on each keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  return (
    <div>
      <Input.TextArea
        value={text}
        rows={rows}
        spellCheck={false}
        style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 12 }}
        onChange={(event) => {
          const next = event.target.value;
          setText(next);
          try {
            const parsed = JSON.parse(next) as unknown;
            setError(null);
            onChange(parsed, null);
          } catch (err) {
            const message = err instanceof Error ? err.message : "JSONが壊れています";
            setError(message);
            onChange(value, message);
          }
        }}
      />
      {error ? <div style={{ color: "#cf1322", marginTop: 4 }}>{error}</div> : null}
    </div>
  );
}
