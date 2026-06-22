"""Core linting engine for DRIPCHECK.

No third-party imports — standard library only.

The engine accepts a list of "emails", where each email is a dict with at
least a ``body`` and optionally ``subject``, ``from``, ``html``, and ``id``
keys. It produces structured :class:`Finding` objects grouped per email and
for the sequence as a whole.

Checks implemented (real logic, not stubs):

* CAN-SPAM: unsubscribe mechanism present (link or mailto)
* CAN-SPAM: physical postal address present
* CAN-SPAM: subject line not deceptive vs. body (RE:/FWD: with no thread)
* Spam-trigger word density in subject and body
* ALL-CAPS / excessive punctuation in subject ("!!!", "$$$")
* Missing or empty subject
* Excessive link count (link-heavy bodies trip filters)
* Text-to-link ratio (image/link-only emails)
* Sequence-level: duplicate subject lines across the drip
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional

TOOL_NAME = "dripcheck"
TOOL_VERSION = "0.7.9"

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

_SEVERITY_ORDER = {SEVERITY_INFO: 0, SEVERITY_WARNING: 1, SEVERITY_ERROR: 2}

# --- detection vocabularies -------------------------------------------------

# Words/phrases commonly weighted by spam filters (SpamAssassin-style).
SPAM_TRIGGER_WORDS = [
    "free", "act now", "limited time", "buy now", "click here", "order now",
    "100% free", "risk-free", "risk free", "guarantee", "guaranteed",
    "cash", "cheap", "discount", "earn money", "make money", "extra income",
    "double your", "no cost", "no fees", "winner", "congratulations",
    "urgent", "viagra", "cialis", "weight loss", "work from home",
    "this isn't spam", "this is not spam", "increase sales", "miracle",
    "satisfaction guaranteed", "credit card", "lowest price", "why pay more",
    "million dollars", "pre-approved", "preapproved", "once in a lifetime",
    "call now", "apply now", "sign up free", "as seen on", "bonus",
]

# Phrases that strongly indicate an unsubscribe mechanism.
UNSUBSCRIBE_PATTERNS = [
    r"unsubscribe",
    r"opt[\s-]?out",
    r"manage (your )?(email )?preferences",
    r"update (your )?(email )?preferences",
    r"email preferences",
    r"stop receiving",
    r"remove me",
]

# Street address heuristic: number + street word (US + common international),
# or PO box. Covers EN/FR/DE/ES/IT keywords so non-US footers are recognised.
_STREET_WORDS = (
    r"(st|street|ave|avenue|blvd|boulevard|rd|road|ln|lane|dr|drive|"
    r"ct|court|way|pl|place|suite|ste|floor|fl|unit|apt|hwy|highway|pkwy|parkway|"
    # International street keywords (number-then-word in many countries).
    r"rue|avenue|boulevard|impasse|allee|allée|"        # French
    r"strasse|straße|str|gasse|weg|platz|allee|"          # German
    r"calle|avenida|paseo|plaza|carrer|"                       # Spanish/Catalan
    r"via|viale|piazza|corso|strada)"                          # Italian
)
_ADDRESS_PATTERNS = [
    re.compile(r"\b\d{1,6}\s+[\w.\- ]{2,40}\b" + _STREET_WORDS + r"\b", re.I),
    # "Rue de la Loi 12" / "Bahnhofstrasse 5" — word-then-number ordering.
    re.compile(r"\b" + _STREET_WORDS + r"\b[\w.\- ]{2,40}\s+\d{1,6}\b", re.I),
    re.compile(r"\bp\.?\s*o\.?\s*box\s+\d+", re.I),
    # City, ST ZIP  (e.g. "Austin, TX 78701")
    re.compile(r"\b[A-Z][A-Za-z.\- ]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"),
    # Postal code + city + country tail (EU-style), e.g.
    # "1040 Brussels, Belgium" or "Berlin, Germany" with a 4-5 digit code.
    re.compile(
        r"\b\d{4,5}\s+[A-Z][A-Za-z.\- ]+,\s*[A-Z][A-Za-z]+\b"
    ),
]

_LINK_RE = re.compile(r"https?://[^\s)\"'>]+", re.I)
_HREF_RE = re.compile(r"href\s*=\s*[\"']([^\"']+)[\"']", re.I)
_MAILTO_RE = re.compile(r"mailto:[^\s)\"'>]+", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[A-Za-z']+")


@dataclass
class Finding:
    """A single lint result."""
    code: str
    severity: str
    message: str
    email_id: Optional[str] = None
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EmailReport:
    email_id: str
    subject: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARNING]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "email_id": self.email_id,
            "subject": self.subject,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class SequenceReport:
    emails: List[EmailReport] = field(default_factory=list)
    sequence_findings: List[Finding] = field(default_factory=list)

    @property
    def all_findings(self) -> List[Finding]:
        out: List[Finding] = list(self.sequence_findings)
        for er in self.emails:
            out.extend(er.findings)
        return out

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.all_findings if f.severity == SEVERITY_ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.all_findings if f.severity == SEVERITY_WARNING)

    @property
    def failed(self) -> bool:
        """True when any error-severity finding exists (CI gate fails)."""
        return self.error_count > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": "dripcheck",
            "summary": {
                "emails": len(self.emails),
                "errors": self.error_count,
                "warnings": self.warning_count,
                "failed": self.failed,
            },
            "sequence_findings": [f.to_dict() for f in self.sequence_findings],
            "emails": [er.to_dict() for er in self.emails],
        }


# --- helpers ----------------------------------------------------------------

def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text)


def _extract_links(email: Dict[str, Any]) -> List[str]:
    links: List[str] = []
    body = email.get("body", "") or ""
    html = email.get("html", "") or ""
    blob = body + "\n" + html
    links.extend(_LINK_RE.findall(blob))
    links.extend(_HREF_RE.findall(html))
    # de-dup preserving order
    seen = set()
    out = []
    for link in links:
        if link not in seen:
            seen.add(link)
            out.append(link)
    return out


def _searchable_text(email: Dict[str, Any]) -> str:
    body = email.get("body", "") or ""
    html = email.get("html", "") or ""
    return _strip_html(body + "\n" + html)


def _has_unsubscribe(email: Dict[str, Any]) -> bool:
    text = _searchable_text(email).lower()
    html = (email.get("html", "") or "").lower()
    for pat in UNSUBSCRIBE_PATTERNS:
        if re.search(pat, text):
            return True
    # An href whose link text/target mentions unsubscribe also counts.
    for href in _HREF_RE.findall(html):
        if "unsubscribe" in href.lower() or "optout" in href.lower():
            return True
    return False


def _has_physical_address(email: Dict[str, Any]) -> bool:
    text = _searchable_text(email)
    for pat in _ADDRESS_PATTERNS:
        if pat.search(text):
            return True
    return False


def _spam_hits(text: str) -> List[str]:
    low = text.lower()
    hits = []
    for word in SPAM_TRIGGER_WORDS:
        if word in low:
            hits.append(word)
    return hits


def _caps_ratio(text: str) -> float:
    words = _WORD_RE.findall(text)
    long_words = [w for w in words if len(w) >= 3]
    if not long_words:
        return 0.0
    caps = sum(1 for w in long_words if w.isupper())
    return caps / len(long_words)


# --- per-email lint ---------------------------------------------------------

def lint_email(email: Dict[str, Any], index: int = 0) -> EmailReport:
    """Lint a single email dict and return its :class:`EmailReport`."""
    email_id = str(email.get("id") or f"email-{index + 1}")
    subject = (email.get("subject") or "").strip()
    body = email.get("body", "") or ""
    text = _searchable_text(email)
    report = EmailReport(email_id=email_id, subject=subject)
    add = report.findings.append

    # --- CAN-SPAM: unsubscribe ---
    if not _has_unsubscribe(email):
        add(Finding(
            code="no-unsubscribe",
            severity=SEVERITY_ERROR,
            message="No unsubscribe/opt-out mechanism found (CAN-SPAM 15 U.S.C. 7704).",
            email_id=email_id,
        ))

    # --- CAN-SPAM: physical postal address ---
    if not _has_physical_address(email):
        add(Finding(
            code="no-physical-address",
            severity=SEVERITY_ERROR,
            message="No valid physical postal address detected (CAN-SPAM requires one).",
            email_id=email_id,
        ))

    # --- subject presence ---
    if not subject:
        add(Finding(
            code="missing-subject",
            severity=SEVERITY_ERROR,
            message="Email has no subject line.",
            email_id=email_id,
        ))
    else:
        # Deceptive subject: RE:/FWD: implying an existing thread.
        if re.match(r"^\s*(re|fwd?)\s*:", subject, re.I):
            add(Finding(
                code="deceptive-subject",
                severity=SEVERITY_WARNING,
                message="Subject starts with RE:/FW: which can be deceptive for a cold send.",
                email_id=email_id,
                detail=subject,
            ))
        # Excessive punctuation / money symbols.
        if re.search(r"!{2,}", subject) or "$$$" in subject or re.search(r"\?{2,}", subject):
            add(Finding(
                code="subject-punctuation",
                severity=SEVERITY_WARNING,
                message="Subject uses excessive punctuation (!!!/???/$$$) that trips spam filters.",
                email_id=email_id,
                detail=subject,
            ))
        # ALL CAPS subject.
        if _caps_ratio(subject) >= 0.5 and len(_WORD_RE.findall(subject)) >= 2:
            add(Finding(
                code="subject-all-caps",
                severity=SEVERITY_WARNING,
                message="Subject is mostly ALL CAPS, a strong spam signal.",
                email_id=email_id,
                detail=subject,
            ))
        if len(subject) > 78:
            add(Finding(
                code="subject-too-long",
                severity=SEVERITY_INFO,
                message=f"Subject is {len(subject)} chars; long subjects get truncated in clients.",
                email_id=email_id,
            ))

    # --- spam trigger words ---
    subj_hits = _spam_hits(subject)
    if subj_hits:
        add(Finding(
            code="spam-words-subject",
            severity=SEVERITY_WARNING,
            message="Spam-trigger word(s) in subject: " + ", ".join(sorted(set(subj_hits))),
            email_id=email_id,
        ))
    body_hits = _spam_hits(text)
    words = max(len(_WORD_RE.findall(text)), 1)
    density = len(body_hits) / words
    if len(body_hits) >= 3 or density > 0.03:
        add(Finding(
            code="spam-words-body",
            severity=SEVERITY_WARNING,
            message=(
                f"High spam-word load in body ({len(body_hits)} hits): "
                + ", ".join(sorted(set(body_hits))[:8])
            ),
            email_id=email_id,
        ))

    # --- body emptiness ---
    if len(text.strip()) < 20:
        add(Finding(
            code="empty-body",
            severity=SEVERITY_ERROR,
            message="Email body is empty or too short to be a real message.",
            email_id=email_id,
        ))

    # --- link checks ---
    links = _extract_links(email)
    if len(links) > 10:
        add(Finding(
            code="too-many-links",
            severity=SEVERITY_WARNING,
            message=f"Email contains {len(links)} links; link-heavy emails are more likely to be filtered.",
            email_id=email_id,
        ))
    # text-to-link ratio: lots of links, almost no prose.
    if links and words < 25 and len(links) >= 2:
        add(Finding(
            code="low-text-link-ratio",
            severity=SEVERITY_WARNING,
            message="Very little text relative to links (image/link-only emails look like spam).",
            email_id=email_id,
        ))

    return report


# --- sequence lint ----------------------------------------------------------

def lint_sequence(emails: Iterable[Dict[str, Any]]) -> SequenceReport:
    """Lint an ordered sequence of emails (the full drip)."""
    emails = list(emails)
    seq = SequenceReport()
    subjects_seen: Dict[str, List[str]] = {}

    for i, email in enumerate(emails):
        er = lint_email(email, index=i)
        seq.emails.append(er)
        key = er.subject.strip().lower()
        if key:
            subjects_seen.setdefault(key, []).append(er.email_id)

    # Sequence-level: duplicate subjects across the drip.
    for subject, ids in subjects_seen.items():
        if len(ids) > 1:
            seq.sequence_findings.append(Finding(
                code="duplicate-subject",
                severity=SEVERITY_WARNING,
                message=f"Subject reused across {len(ids)} emails ({', '.join(ids)}); vary subjects in a drip.",
                detail=subject,
            ))

    if not emails:
        seq.sequence_findings.append(Finding(
            code="empty-sequence",
            severity=SEVERITY_ERROR,
            message="Sequence contains no emails.",
        ))

    return seq


# --- loading ----------------------------------------------------------------

def _coerce_emails(data: Any) -> List[Dict[str, Any]]:
    """Accept a list of emails, or an object with an 'emails'/'sequence' key."""
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("emails") or data.get("sequence") or [data]
    else:
        raise ValueError("Unsupported sequence format: expected list or object.")
    out: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each email must be a JSON object.")
        out.append(item)
    return out


def load_sequence(path: str) -> List[Dict[str, Any]]:
    """Load a sequence from a JSON file path.

    The file may be either a JSON array of email objects, or an object with
    an ``emails`` (or ``sequence``) array.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return _coerce_emails(data)


def loads_sequence(text: str) -> List[Dict[str, Any]]:
    """Parse a sequence from a JSON string."""
    return _coerce_emails(json.loads(text))


# --- exporters: SARIF + CSV -------------------------------------------------

# SARIF maps dripcheck severities onto its three levels.
_SARIF_LEVEL = {
    SEVERITY_ERROR: "error",
    SEVERITY_WARNING: "warning",
    SEVERITY_INFO: "note",
}


def to_sarif(report: "SequenceReport") -> Dict[str, Any]:
    """Render a :class:`SequenceReport` as a SARIF 2.1.0 log.

    SARIF (Static Analysis Results Interchange Format) is the format GitHub
    code-scanning, Azure DevOps, and many CI dashboards ingest natively, so a
    ``dripcheck lint ... --format sarif`` artifact surfaces deliverability
    findings as annotations right on the pull request.

    Each finding becomes a SARIF *result*; its ``code`` is registered as a
    reusable *rule* so dashboards can group and de-duplicate over time. The
    email id (or ``sequence``) is recorded as a logical location so reviewers
    can tell which message in the drip tripped the rule.
    """
    rules: "Dict[str, Dict[str, Any]]" = {}
    results: List[Dict[str, Any]] = []

    def _add(f: Finding) -> None:
        if f.code not in rules:
            rules[f.code] = {
                "id": f.code,
                "name": "".join(p.capitalize() for p in f.code.split("-")),
                "shortDescription": {"text": f.message[:120]},
                "defaultConfiguration": {"level": _SARIF_LEVEL.get(f.severity, "note")},
            }
        loc = f.email_id or "sequence"
        result: Dict[str, Any] = {
            "ruleId": f.code,
            "level": _SARIF_LEVEL.get(f.severity, "note"),
            "message": {"text": f.message + (f"\n{f.detail}" if f.detail else "")},
            "locations": [{
                "logicalLocations": [{"name": loc, "kind": "email"}],
            }],
        }
        results.append(result)

    for f in report.sequence_findings:
        _add(f)
    for er in report.emails:
        for f in er.findings:
            _add(f)

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": TOOL_NAME,
                    "version": TOOL_VERSION,
                    "informationUri": "https://github.com/cognis-digital/dripcheck",
                    "rules": list(rules.values()),
                }
            },
            "results": results,
        }],
    }


_CSV_FIELDS = ["email_id", "subject", "severity", "code", "message", "detail"]


def to_csv(report: "SequenceReport") -> str:
    """Render every finding as a CSV row (header + one row per finding).

    Handy for triage in a spreadsheet or for diffing two runs. Sequence-level
    findings use an ``email_id`` of ``sequence`` and an empty subject.
    """
    subjects = {er.email_id: er.subject for er in report.emails}
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for f in report.sequence_findings:
        writer.writerow({
            "email_id": f.email_id or "sequence",
            "subject": "",
            "severity": f.severity,
            "code": f.code,
            "message": f.message,
            "detail": f.detail or "",
        })
    for er in report.emails:
        for f in er.findings:
            writer.writerow({
                "email_id": f.email_id or er.email_id,
                "subject": subjects.get(f.email_id or er.email_id, er.subject),
                "severity": f.severity,
                "code": f.code,
                "message": f.message,
                "detail": f.detail or "",
            })
    return buf.getvalue()
