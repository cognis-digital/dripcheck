# Demo 08 — Stdin piping and the CI gate

A single clean product-release email used to show two workflow patterns:
reading a sequence from **stdin** (`-`) and using `dripcheck` as a **pre-send
CI gate** via its exit code.

## Where this comes from

A product-update / release-note email — the kind a CI job lints right before
it is queued for send. Linting from stdin lets you generate the sequence in
one step and pipe it straight into the gate without a temp file.

## Run it

```bash
# from a file:
python -m dripcheck lint demos/08-stdin-ci-gate/sequence.json

# from stdin (pipe it in):
cat demos/08-stdin-ci-gate/sequence.json | python -m dripcheck lint -

# as a CI gate — block the pipeline on any error:
cat demos/08-stdin-ci-gate/sequence.json | python -m dripcheck lint - || {
  echo "deliverability gate failed"; exit 1;
}
```

## Expected result

Clean email, exit `0` (PASS), no findings. Swap in a broken sequence (e.g.
`demos/03-cold-outreach-saas/sequence.json`) and the same pipeline exits `1`,
failing the build.

## How to act

Drop the `cat ... | dripcheck lint -` line into your send pipeline. Add
`--strict` if you want warnings (spam words, duplicate subjects) to fail too.
