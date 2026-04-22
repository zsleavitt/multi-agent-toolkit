# Invalid Swarm Examples

These files intentionally fail validation. Used by `scripts/validate_swarm.py` tests.

| File | Reason | Caught by |
|------|--------|-----------|
| `wrong-consensus.json` | `majority-vote` not valid for `dispatch_mode: variant` | JSON Schema |
| `majority-vote-two-candidates.json` | `majority-vote` requires ≥3 candidates | Python validation |
