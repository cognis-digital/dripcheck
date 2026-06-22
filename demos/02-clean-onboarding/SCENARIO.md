# Demo 02 — Clean onboarding drip (the passing baseline)

A real-world, fully compliant 3-email SaaS onboarding sequence. Every email
has an unsubscribe/preferences link, a physical postal address, a real
subject, and substantive body text. This is what "green" looks like.

## Where this comes from

Lifecycle/onboarding sequences are the most common drip a growth team ships.
This one is modeled on a standard "welcome → activation → first value"
cadence. Use it as the reference for what a compliant template should contain
before you wire `dripcheck` into CI.

## Run it

```bash
python -m dripcheck lint demos/02-clean-onboarding/sequence.json
# strict mode (warnings fail too) — should STILL pass:
python -m dripcheck lint demos/02-clean-onboarding/sequence.json --strict
```

## Expected result

No errors and no warnings. The summary line reads `PASS` and the process
exits `0`. In `--format json`, `summary.failed` is `false`, `summary.errors`
is `0`, and `summary.warnings` is `0`.

## How to act

Use this as your golden template. When you fork a new sequence, diff it
against this one — every email should keep the unsubscribe link and the
postal-address footer.
