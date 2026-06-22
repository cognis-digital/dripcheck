# Demo 06 — HTML link-roundup emails (parsing + link checks)

Two HTML-only "link digest" emails. This demo exercises the linter's HTML
handling: it parses `href` targets, strips tags before counting words, and
flags emails that are mostly links with little prose — a classic filter
trigger for newsletters and "weekly roundup" sends.

## Where this comes from

Curated link-digest newsletters are common and easy to get wrong: editors
paste a wall of links and forget the body needs real text. Both emails here
*are* compliant (the unsubscribe link and postal address live inside the
HTML), so the only issues are deliverability, not legal.

## Run it

```bash
python -m dripcheck lint demos/06-html-link-heavy/sequence.json
# emit SARIF for GitHub code-scanning annotations:
python -m dripcheck lint demos/06-html-link-heavy/sequence.json --format sarif > drip.sarif
```

## Expected result

Process exits `0` (warnings only, no errors). Findings:

- **digest-1** — `low-text-link-ratio` (4 links, almost no prose).
- **digest-2** — `too-many-links` (13 links, over the threshold) **and**
  `low-text-link-ratio`.

## How to act

Add a sentence or two of editorial context around each link, and trim very
long roundups. Run with `--strict` if you want these warnings to block CI.
