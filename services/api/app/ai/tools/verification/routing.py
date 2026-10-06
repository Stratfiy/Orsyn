"""Check type to provider name. Only "fake" is allowed until the founder approves a provider."""

from app.modules.verification.policy import CheckType

ALLOWED_PROVIDERS: frozenset[str] = frozenset({"fake"})

ROUTES: dict[CheckType, str] = {
    CheckType.GSTIN: "fake",
    CheckType.PAN: "fake",
    CheckType.NAME_MATCH: "fake",
    CheckType.UDYAM: "fake",
    CheckType.IEC: "fake",
    CheckType.CIN: "fake",
}


class UnroutableCheck(Exception):  # noqa: N818
    """No allowed provider for this check type."""


def provider_name_for(check: CheckType) -> str:
    name = ROUTES.get(check)
    if name is None or name not in ALLOWED_PROVIDERS:
        raise UnroutableCheck(f"no allowed provider for check {check.value!r}")
    return name
