"use client";

import Form from "@rjsf/antd";
import validator from "@rjsf/validator-ajv8";
import { Alert } from "antd";
import type { RJSFSchema } from "@rjsf/utils";

export function SchemaForm({
  schema,
  formData,
  onChange,
  disabled,
}: {
  schema: Record<string, unknown> | null | undefined;
  formData: unknown;
  onChange: (data: unknown) => void;
  disabled?: boolean;
}) {
  if (!schema || schema.type !== "object") {
    return <Alert type="warning" showIcon message="スキーマがオブジェクトではないため、フォームを出せません。" />;
  }
  return (
    <Form
      schema={schema as RJSFSchema}
      formData={formData}
      validator={validator}
      disabled={disabled}
      liveValidate={false}
      showErrorList={false}
      onChange={(event) => onChange(event.formData)}
      uiSchema={{ "ui:submitButtonOptions": { norender: true } }}
    />
  );
}
