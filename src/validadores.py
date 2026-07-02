from __future__ import annotations

import re
from typing import Any


PLACA_RE = re.compile(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", re.IGNORECASE)
RENAVAM_RE = re.compile(r"\b\d{9,11}\b")
VALOR_RE = re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}|\b\d+,\d{2}\b")
DATA_RE = re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])/(?:0?[1-9]|1[0-2])/(?:\d{2}|\d{4})\b")


def validar_e_complementar(dados: dict[str, Any], texto: str) -> dict[str, Any]:
    resultado = dict(dados)

    if not resultado.get("placa"):
        resultado["placa"] = _primeiro_match(PLACA_RE, texto)
    elif isinstance(resultado["placa"], str):
        resultado["placa"] = resultado["placa"].upper().strip()

    if not resultado.get("renavam"):
        resultado["renavam"] = _primeiro_match(RENAVAM_RE, texto)

    if not resultado.get("valor"):
        resultado["valor"] = _primeiro_match(VALOR_RE, texto)

    if not resultado.get("data_pagamento"):
        resultado["data_pagamento"] = _primeiro_match(DATA_RE, texto)

    return resultado


def _primeiro_match(regex: re.Pattern[str], texto: str) -> str | None:
    match = regex.search(texto or "")
    return match.group(0).strip() if match else None

