# core/engine/normalize.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.engine.types import CurriculumData


@dataclass
class NormalizationError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def _norm_basic(raw: str) -> str:
    s = str(raw).strip()
    s = s.replace(" ", "")
    s = s.rstrip(".")
    return s


def _strip_prefix(s: str) -> str:
    up = s.upper()
    if up.startswith("CEV"):
        return s[3:]
    if up.startswith("CE"):
        return s[2:]
    if up.startswith("DO"):
        return s[2:]
    if up.startswith("SB"):
        return s[2:]
    if up.startswith("SSBB"):
        return s[4:]
    return s


def _resolve_ssbb_shortcut(code: str, ssbb_set: set[str]) -> str:
    # Si existe tal cual, OK
    if code in ssbb_set:
        return code

    # Resolver por sufijo con frontera "."
    # Ej: "A.1" -> "1.A.1" si existe y es único
    candidates = [c for c in ssbb_set if c == code or c.endswith("." + code)]

    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) > 1:
        preview = ", ".join(sorted(candidates)[:20])
        raise NormalizationError(f"SSBB ambiguo '{code}'. Coincidencias: {preview}")

    return code


def normalize_user_code(raw: str, data: CurriculumData) -> str:
    s = _norm_basic(raw)
    s = _strip_prefix(s)
    s = _norm_basic(s)

    validos = data.ssbb_set | data.ce_set | data.cev_set | data.do_set
    if s in validos:
        return s

    # Intentar resolver atajos de SSBB (A.1 -> 1.A.1)
    resolved = _resolve_ssbb_shortcut(s, data.ssbb_set)
    return resolved


def normalize_codes(raw_codes: Iterable[str], data: CurriculumData) -> list[str]:
    out: list[str] = []
    errors: list[str] = []

    for raw in raw_codes:
        try:
            out.append(normalize_user_code(raw, data))
        except NormalizationError as e:
            errors.append(str(e))

    if errors:
        raise NormalizationError(" | ".join(errors))

    # Validación final
    validos = data.ssbb_set | data.ce_set | data.cev_set | data.do_set
    invalidos = [c for c in out if c not in validos]
    if invalidos:
        raise NormalizationError(f"Códigos no encontrados: {invalidos}")

    return out
