# Gumloop examples (MAT-5)

Files in this folder support the **MAT-5** prototype described in `docs/prototypes/mat-5-gumloop.md`.

| File | Purpose |
|------|---------|
| `input-names.conventions.json` | Recommended Gumloop **Input** node `input_name` strings and short descriptions for MAT-aligned flows. |
| `start-pipeline.request.example.json` | Example **`start_pipeline`** JSON body (redact secrets; replace `saved_item_id` / `user_id`). |

CI / local check (same deps as other validators): `python scripts/validate_gumloop_examples.py` — ensures JSON in this folder parses and that **`mat2_request_json`** strings in `start-pipeline.request.example.json` validate against MAT-2 `request.schema.json`.

Optional CLI (no extra deps): `python scripts/gumloop_start_pipeline.py --help` from repo root (requires `GUMLOOP_API_KEY` and `GUMLOOP_USER_ID`).

Use Gumloop’s docs for authentication and for mapping `pipeline_inputs` to your canvas Input nodes.
