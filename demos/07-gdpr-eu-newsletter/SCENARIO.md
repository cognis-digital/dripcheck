# Demo 07 — EU/GDPR newsletter with a non-US postal address

A 2-email EU briefing with explicit opt-in language, opt-out + preference
links, and a **Belgian** postal address. This demo shows the linter
recognising international address footers (French/German/Spanish/Italian
street keywords and `postal-code City, Country` tails), not just US
`City, ST ZIP`.

## Where this comes from

A double-opt-in EU newsletter footer. Before the international-address
improvement, a footer like `12 Rue de la Loi, 1040 Brussels, Belgium` was
wrongly flagged `no-physical-address`; now it passes.

## Run it

```bash
python -m dripcheck lint demos/07-gdpr-eu-newsletter/sequence.json
```

## Expected result

Process exits `0` (PASS) — **no findings**. The unsubscribe/opt-out variants
("opt-out", "manage your preferences", "unsubscribe") are all detected, and
the Brussels address satisfies the physical-address requirement.

## How to act

Use this as the template for EU/international sends. If you localise the
footer further, keep a recognisable street keyword and a `postal-code City,
Country` line so the address check keeps passing.
