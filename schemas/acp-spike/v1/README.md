# ACP spike schemas (`acp-spike@v1`)

**Not a production wire format.** Illustrative JSON Schema for the MAT-100 spike:
how a MAT-2 governance envelope could drive an ACP session without replacing MAT
routing/idempotency.

See [`research/2026-07-acp-spike.md`](../../research/2026-07-acp-spike.md).

| File | Purpose |
|------|---------|
| `manifest.json` | Bundle id + note that this is spike-only |
| `mat-over-acp.request.schema.json` | Sketch: MAT fields + ACP session hints |
| `examples/implement-via-acp.json` | Example payload |

Do **not** register this bundle in `config/schema-registry.json` until a
follow-on implementation ticket promotes it.
