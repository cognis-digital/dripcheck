# Demo 05 — Compliant emails, but a sequence-level smell

Every individual email here is clean (unsubscribe + address + real body), so
per-email linting passes. The problem only shows up when you look at the drip
as a whole: all three reuse the exact same subject line, which hurts open
rates and looks like a broken automation.

## Where this comes from

A nurture series where someone hard-coded the subject in the template and
forgot to vary it per send. This is the case `dripcheck`'s sequence-level
checks exist for — no single email is "wrong."

## Run it

```bash
python -m dripcheck lint demos/05-duplicate-subjects/sequence.json
```

## Expected result

The per-email sections show **no findings**. The `[sequence]` section reports
a `duplicate-subject` **warning** naming all three email ids. Because it is a
warning (not an error), the default run exits `0` — but `--strict` turns it
into a failure:

```bash
python -m dripcheck lint demos/05-duplicate-subjects/sequence.json --strict   # exits 1
```

## How to act

Give each touch a distinct subject. Use `--strict` in CI if you want
duplicate subjects to block the release.
