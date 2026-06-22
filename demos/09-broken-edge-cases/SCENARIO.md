# Demo 09 — Edge cases: missing subject, empty body, oversized subject

A deliberately broken 3-email set that isolates the structural checks:
a missing subject line, an effectively empty body, and an oversized subject.
Useful as a regression fixture and to see how each severity level renders.

## Where this comes from

The kinds of mistakes that slip through when a template variable fails to
render or a draft gets queued by accident — empty bodies, blank subjects,
and runaway subject lines from a bad merge field.

## Run it

```bash
python -m dripcheck lint demos/09-broken-edge-cases/sequence.json
python -m dripcheck lint demos/09-broken-edge-cases/sequence.json --format json | jq '.summary'
```

## Expected result

Process exits `1` (FAIL). Findings:

- **missing-subject** — `missing-subject` (error): no subject line.
- **empty-body** — `empty-body` (error) plus `no-unsubscribe` and
  `no-physical-address` (the stub body has neither).
- **long-subject** — `subject-too-long` (**info** only): a 143-char subject
  that mail clients will truncate. Info findings do not fail the build on
  their own; here the build fails because of the two error-level emails.

## How to act

Treat `missing-subject` and `empty-body` as must-fix before send. The
`subject-too-long` info is advisory — trim subjects under ~78 chars for
better inbox rendering.
