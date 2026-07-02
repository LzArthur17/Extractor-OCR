from __future__ import annotations

import json
import re
from typing import Any

import requests


DEFAULT_FIELDS = [
    "tipo_documento",
    "placa",
    "renavam",
    "valor",
    "data_pagamento",
    "data_vencimento",
    "beneficiario",
    "banco",
    "codigo_transacao",
    "numero_documento",
]


class AgenteErro(RuntimeError):
    pass


def extrair_campos_com_ollama(
    texto: str,
    fields: list[str] | None = None,
    model: str = "llama3.1",
    ollama_url: str = "http://localhost:11434",
    timeout: int = 120,
) -> dict[str, Any]:
    campos = fields or DEFAULT_FIELDS
    prompt = montar_prompt(texto=texto, campos=campos)

    resposta = requests.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=timeout,
    )
    resposta.raise_for_status()

    conteudo = resposta.json().get("response", "")
    dados = _parse_json(conteudo)
    return {campo: dados.get(campo) for campo in campos}


def revisar_campos_crlv_com_ollama(
    texto: str,
    campos_extraidos: dict[str, Any],
    fields: list[str],
    model: str = "llama3.1",
    ollama_url: str = "http://localhost:11434",
    timeout: int = 120,
) -> dict[str, Any]:
    prompt = montar_prompt_revisao_crlv(texto, campos_extraidos, fields)
    resposta = requests.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=timeout,
    )
    resposta.raise_for_status()
    dados = _parse_json(resposta.json().get("response", ""))
    return {campo: dados.get(campo) for campo in fields}


def montar_prompt(texto: str, campos: list[str]) -> str:
    lista_campos = "\n".join(f"- {campo}" for campo in campos)
    return f"""
Voce e um extrator de dados de documentos brasileiros.

Extraia apenas os campos solicitados.
Retorne somente JSON valido.
Nao invente informacoes.
Se um campo nao existir no texto, retorne null.
Mantenha valores monetarios no formato encontrado.
Mantenha datas no formato DD/MM/AAAA quando possivel.

Campos:
{lista_campos}

Texto do documento:
\"\"\"
{texto[:20000]}
\"\"\"
""".strip()


def montar_prompt_revisao_crlv(texto: str, campos_extraidos: dict[str, Any], campos: list[str]) -> str:
    lista_campos = "\n".join(f"- {campo}" for campo in campos)
    return f"""
Voce e um auditor de extracao de dados de CRLV brasileiro.

Confira os campos ja extraidos usando somente o texto OCR abaixo.
Corrija apenas quando o valor estiver explicitamente no texto.
Se o campo nao estiver legivel ou nao existir no texto, retorne null.
Nao invente dados e nao use conhecimento externo.
Retorne somente JSON valido com estes campos:
{lista_campos}

Campos extraidos pelas regras:
{json.dumps(campos_extraidos, ensure_ascii=False, indent=2)}

Texto OCR:
\"\"\"
{texto[:22000]}
\"\"\"
""".strip()


def _parse_json(conteudo: str) -> dict[str, Any]:
    try:
        resultado = json.loads(conteudo)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", conteudo, flags=re.DOTALL)
        if not match:
            raise AgenteErro(f"O modelo nao retornou JSON valido: {conteudo[:300]}")
        resultado = json.loads(match.group(0))

    if not isinstance(resultado, dict):
        raise AgenteErro("O modelo retornou JSON, mas nao retornou um objeto.")

    return resultado
