# Demo 04 — The everything-wrong promo blast

A single promotional email that maxes out almost every spam signal at once.
Useful as a worst-case regression fixture and to see the full vocabulary of
findings in one run.

## Where this comes from

This is a synthetic "deal blast" built from the SpamAssassin-style trigger
vocabulary the linter ships with. It is intentionally over the top so each
rule fires.

## Run it

```bash
python -m dripcheck lint demos/04-promo-spam-traps/sequence.json
# export to a spreadsheet for the marketing team:
python -m dripcheck lint demos/04-promo-spam-traps/sequence.json --format csv > findings.csv
```

## Expected result

Process exits `1` (FAIL). Findings on **blast-1** include:

- `no-unsubscribe` and `no-physical-address` (errors).
- `subject-all-caps`, `subject-punctuation` (`!!!`, `$$$`),
  `spam-words-subject`, and `spam-words-body` (high spam-word load).

## How to act

This template is unsalvageable as-is — rewrite the subject in sentence case,
strip the trigger words, add the legal footer, and aim for a real
text-to-link ratio. Treat the CSV as a checklist.
