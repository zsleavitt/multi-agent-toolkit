# Example workflows

These patterns assume skills are [installed](installing-skills.md), **`ai-team.repo.json`** exists when you use `/ticket`, and optional **`mat-config.json`** is present for `mat_runtime`.

## Implement a feature

1. **Plan (optional)** — `/plan <goal>` to decompose work and surface risks (or plan in freeform chat if you prefer).
2. **Implement** — `/develop <concrete task>` so the orchestrated flow coordinates implementation and follow-ups (see `lib/skills/develop/instructions.md` for the full contract).
3. **Test** — `/test <scope>` to focus the tester agent on new code paths.
4. **Review** — `/review-pr Review staged changes` (or a PR number / URL if your skill invocation supports it).
5. **Tickets** — `/ticket create "..."` / `/ticket update ...` if you track work in Linear, GitHub Issues, etc.

**Git-heavy steps** (branch, commit, push) follow **MAT-1** via your configured git executor CLI — not via Codex MAT-2 ops. Keep that split when you automate.

## Fix a bug

1. **Diagnose** — `/diagnose <symptoms or failure>` for structured investigation.
2. **Develop** — `/develop Fix: <summary>` once root cause is understood.
3. **Test** — `/test <regression or module>` to lock behavior.
4. **Review** — `/review-pr` on the fix before merge.

## Review a pull request

- **Local / staged** — `/review-pr Review staged changes for security and correctness`
- **Numbered PR** — `/review-pr 42` or full URL, depending on how you pass targets (see `lib/skills/review-pr/instructions.md`).

For GitHub comment posting and advanced options, see the skill docs and any provider-specific flags.

## Finish a branch (work items)

If you use **`/finish-branch`**, it reads **`work_item_source`** from `ai-team.repo.json` and transitions or closes items after merge workflows. See **`lib/skills/finish-branch/`** and `.claude/skills/finish-branch/SKILL.md`.

## Direct `mat_runtime` (no slash command)

Useful in CI or scripts:

```bash
python -m mat_runtime list-agents
python -m mat_runtime invoke --agent coder --instruction "Add input validation to parse_header()"
python -m mat_runtime invoke --request ./path/to/codex-request.json
```

Ensure `MAT_*` env vars or default paths resolve schemas if you run outside a standard checkout.

## Validation in CI

Run the same validators as the toolkit (adjust paths to your submodule):

```bash
python vendor/multi-agent-toolkit/scripts/validate_ai_team_repo_profile.py
python vendor/multi-agent-toolkit/scripts/validate_provider_config.py
# …other bundles you depend on
```

See root [README — Validation](../../README.md#validation) for the full list.
