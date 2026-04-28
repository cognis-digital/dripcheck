# Demo 01 — Basic email sequence lint

This demo runs DRIPCHECK against a small 3-email cold/drip sequence in
`sequence.json`. The file is deliberately seeded with realistic problems so
you can see the linter actually catch them.

## Run it

```bash
python -m dripcheck lint demos/01-basic/sequence.json
# or JSON for CI:
python -m dripcheck lint demos/01-basic/sequence.json --format json | jq .summary
```

## What the emails contain

- **welcome-1** — A clean, compliant welcome email: it has an unsubscribe
  link and a physical postal address. It should produce **no errors**.
- **promo-2** — A spammy promo: ALL-CAPS subject with `!!!`, multiple
  spam-trigger words ("FREE", "act now", "100% free", "guarantee"), **no
  unsubscribe link**, and **no physical address**.
- **followup-3** — A deceptive `RE:` follow-up that also reuses the same
  subject pattern and is missing its physical address.

## Expected result

The linter reports **errors** (missing unsubscribe / missing physical
address / etc.) for the bad emails, so the process **exits with code 1** —
making it usable as a pre-send CI gate. Findings include codes like
`no-unsubscribe`, `no-physical-address`, `spam-words-subject`,
`subject-all-caps`, `subject-punctuation`, and `deceptive-subject`.

The summary line / JSON `summary.failed` will be `true`.
