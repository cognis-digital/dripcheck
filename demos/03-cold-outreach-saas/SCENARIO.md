# Demo 03 — B2B cold outreach with the classic mistakes

A 3-step cold sales sequence that *reads* fine to a human but trips several
deliverability and compliance rules. This is the most common pattern
`dripcheck` is meant to catch: an SDR templated a sequence, faked a thread,
and forgot the legal footer on the first two touches.

## Where this comes from

This mirrors a typical 3-touch cold cadence exported from an outreach tool.
"Reply 'no thanks'" feels like an opt-out to the writer, but it is not a
working unsubscribe mechanism, and `RE:`/`FWD:` on a first-contact email is
the deceptive-subject pattern CAN-SPAM warns about.

## Run it

```bash
python -m dripcheck lint demos/03-cold-outreach-saas/sequence.json
python -m dripcheck lint demos/03-cold-outreach-saas/sequence.json --format json | jq '.summary'
```

## Expected result

Process exits `1` (FAIL). Findings include:

- `no-unsubscribe` on **cold-1** and **cold-2** (a "reply no thanks" line is
  not a detectable opt-out; only **cold-3** has a real link).
- `no-physical-address` on all three (no postal footer anywhere).
- `deceptive-subject` on **cold-2** (`RE:`) and **cold-3** (`FWD:`).

## How to act

Add the postal-address + unsubscribe footer to *every* email in the sequence,
not just the last one, and drop the fake `RE:`/`FWD:` prefixes. Re-run until
it exits `0`.
