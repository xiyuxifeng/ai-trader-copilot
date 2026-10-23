# SourceAdapter v0

## 目的

统一用户粘贴、文件上传和未来链接获取的输出。来源适配器只负责获取与规范化，不判断交易价值，不创建规则。

## 输入

```text
SourceRequest
├── kind: pasted_text | uploaded_file | url
├── supplied_title?: string
├── content?: bytes | string
├── source_url?: https URL
└── requested_at: timestamp with timezone
```

## 输出

```text
SourceDocumentEnvelope
├── adapter_name: string
├── adapter_version: string
├── source_kind: string
├── canonical_url?: string
├── title?: string
├── author?: string
├── published_at?: timestamp with timezone
├── fetched_at: timestamp with timezone
├── media_type: string
├── language?: string
├── normalized_text: string
├── content_sha256: string
├── completeness: complete | partial | unknown
├── usage_policy: full_text_allowed | evidence_only | reference_only | unknown
└── warnings: string[]
```

## 不变量

- `normalized_text` 与内容指纹必须确定性生成。
- 无法确认发布时间时保持空值，不能用抓取时间替代。
- URL 只允许 HTTPS，并阻止本机、内网、云元数据和重定向越权。
- 上传文件必须在解析前完成大小、类型和解压限制。
- 适配器不得调用 LLM，不得返回规则或价值判断。
- 抓取器只在来源系统验证通过后实现；v1 优先粘贴和上传。

