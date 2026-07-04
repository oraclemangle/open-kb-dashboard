"""redaction.py -- credential-only egress scrubber for open-kb-dashboard.

Stdlib only. NO third-party imports, NO import-time side effects.

POLICY (creds-only):
  REDACT only real credentials/secrets:
    - PEM private keys ("-----BEGIN ... PRIVATE KEY----- ... -----END ... PRIVATE KEY-----")
    - password / passwd / pwd = value
    - api[_-]?key = value
    - client[_-]?secret = value
    - secret / token = <long value>
    - bearer <20+ chars>
    - AWS AKIA[0-9A-Z]{16} access key ids + 40-char secret-access-key assignments
  DO NOT redact: hostnames, generic identifiers, or other non-secret operational data --
  this is a credential scrubber, not a topology/PII redactor. Callers wanting stricter
  behaviour should layer their own rules on top.
  Replacement token format: [REDACTED:KIND]

Fail-closed contract: the public functions are exception-safe, but callers should still
treat any exception from scrub/scrub_obj as "do not send" and avoid forwarding raw text.
"""
from __future__ import annotations

import re

REDACTION_VERSION = "generic-creds-only-1"

# A "value" terminator: stop at whitespace, quotes, commas, or end-of-line.
_VAL = r"""[^\s'"]+"""

# PEM private key block (multiline). Mask the whole block.
_RE_PEM = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.S,
)

# Optional closing quote (+ optional space) between a key word and the ':'/'=' separator.
# This is what lets the quoted-key JSON/YAML form match, e.g.  "password": "hunter2".
_SEP = r"""["']?\s*[:=]\s*"""

# password / passwd / pwd = value   (bare key=val, ini/toml, AND quoted-key JSON/YAML)
_RE_PASSWORD = re.compile(
    r"""(?P<label>\b(?:password|passwd|pwd)\b""" + _SEP + r""")(?P<q>['"]?)(?P<val>""" + _VAL + r""")""",
    re.I,
)

# api_key / api-key / apikey = value
_RE_APIKEY = re.compile(
    r"""(?P<label>\bapi[_-]?key\b""" + _SEP + r""")(?P<q>['"]?)(?P<val>""" + _VAL + r""")""",
    re.I,
)

# client_secret / client-secret = value
_RE_CLIENT_SECRET = re.compile(
    r"""(?P<label>\bclient[_-]?secret\b""" + _SEP + r""")(?P<q>['"]?)(?P<val>""" + _VAL + r""")""",
    re.I,
)

# AWS secret access key assignment (40-char base64-ish value). Check BEFORE the generic
# secret/token rule so it claims its own KIND.
_RE_AWS_SECRET = re.compile(
    r"""(?P<label>\baws[_-]?secret[_-]?access[_-]?key\b""" + _SEP + r""")(?P<q>['"]?)(?P<val>[A-Za-z0-9/+=]{40})""",
    re.I,
)

# generic secret / token = <long value> (>= 8 chars, avoids masking trivial words)
_RE_SECRET_TOKEN = re.compile(
    r"""(?P<label>\b(?:secret|token)\b""" + _SEP + r""")(?P<q>['"]?)(?P<val>[^\s'"]{8,})""",
    re.I,
)

# bearer <20+ chars>
_RE_BEARER = re.compile(
    r"(?P<label>\bbearer\s+)(?P<val>[A-Za-z0-9._\-/+=~]{20,})",
    re.I,
)

# AWS access key id (standalone token)
_RE_AKIA = re.compile(r"\bAKIA[0-9A-Z]{16}\b")


def _mask_value(kind):
    """Return a sub() repl that keeps the label/assignment and masks just the value."""
    def _repl(m):
        return m.group("label") + "[REDACTED:%s]" % kind
    return _repl


# Ordered rules. PEM and the AWS-secret/specific rules run before the generic secret/token rule.
_RULES = [
    (_RE_PEM, "PRIVATE_KEY", lambda m: "[REDACTED:PRIVATE_KEY]"),
    (_RE_PASSWORD, "PASSWORD", _mask_value("PASSWORD")),
    (_RE_AWS_SECRET, "AWS_SECRET", _mask_value("AWS_SECRET")),
    (_RE_APIKEY, "API_KEY", _mask_value("API_KEY")),
    (_RE_CLIENT_SECRET, "CLIENT_SECRET", _mask_value("CLIENT_SECRET")),
    (_RE_SECRET_TOKEN, "SECRET", _mask_value("SECRET")),
    (_RE_BEARER, "BEARER", lambda m: m.group("label") + "[REDACTED:BEARER]"),
    (_RE_AKIA, "AWS_KEY_ID", lambda m: "[REDACTED:AWS_KEY_ID]"),
]


def scrub(text):
    """Redact ONLY credentials/secrets. Returns (scrubbed_text, num_redactions).

    Exception-safe: on any internal error returns a scrub-error token rather than the
    original text, so failures do not become egress leaks.
    """
    if text is None:
        return text, 0
    if not isinstance(text, str):
        return text, 0
    try:
        out = text
        total = 0
        for rx, _kind, repl in _RULES:
            count = 0

            def _counting_repl(m, _repl=repl):
                nonlocal count
                count += 1
                return _repl(m)

            out = rx.sub(_counting_repl, out)
            total += count
        return out, total
    except Exception:
        return "[REDACTED:SCRUB_ERROR]", 1


def scrub_obj(obj):
    """Recursively scrub all string values inside dict/list/tuple/str. Returns (obj, total_count).

    Non-string scalars (int/float/bool/None) pass through unchanged.

    Exception-safe: on any internal error returns a scrub-error token with count 1.
    """
    try:
        return _scrub_obj_inner(obj)
    except Exception:
        return "[REDACTED:SCRUB_ERROR]", 1


def _scrub_obj_inner(obj):
    if isinstance(obj, str):
        return scrub(obj)
    if isinstance(obj, dict):
        total = 0
        new = {}
        for k, v in obj.items():
            nv, c = _scrub_obj_inner(v)
            new[k] = nv
            total += c
        return new, total
    if isinstance(obj, list):
        total = 0
        new = []
        for v in obj:
            nv, c = _scrub_obj_inner(v)
            new.append(nv)
            total += c
        return new, total
    if isinstance(obj, tuple):
        total = 0
        items = []
        for v in obj:
            nv, c = _scrub_obj_inner(v)
            items.append(nv)
            total += c
        return tuple(items), total
    # int / float / bool / None / other scalars: unchanged.
    return obj, 0
