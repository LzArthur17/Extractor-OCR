from __future__ import annotations

from typing import Any


def montar_campos_formulario(campos: dict[str, Any]) -> dict[str, Any]:
    return {
        "cliente": campos.get("proprietario"),
        "documento_cliente": campos.get("cpf_cnpj"),
        "placa": campos.get("placa"),
        "chassi": campos.get("chassi"),
        "renavam": campos.get("renavam"),
        "marca_modelo": campos.get("marca_modelo"),
        "cor": campos.get("cor"),
        "combustivel": campos.get("combustivel"),
        "categoria": campos.get("categoria"),
        "ano_fabricacao": campos.get("ano_fabricacao"),
        "ano_modelo": campos.get("ano_modelo"),
        "crv": campos.get("codigo_crv"),
        "uf_origem": campos.get("uf"),
        "doc_proprietario": campos.get("cpf_cnpj"),
    }

