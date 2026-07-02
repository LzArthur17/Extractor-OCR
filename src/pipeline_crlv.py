from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.crlv_extrator import extrair_crlv
from src.ocr import extrair_texto_documento, extrair_texto_documento_refinado
from src.qualidade import avaliar_qualidade


def extrair_crlv_com_retry_ocr(
    arquivo: Path,
    nome_arquivo: str | None = None,
    idioma: str = "por",
    max_pages: int | None = None,
    retry_min_score: int = 85,
    retry_timeout_seconds: int = 12,
    enable_retry: bool = True,
    texto_inicial: str | None = None,
) -> dict[str, Any]:
    nome = nome_arquivo or arquivo.name
    texto = texto_inicial if texto_inicial is not None else extrair_texto_documento(arquivo, idioma=idioma, max_pages=max_pages)
    campos = extrair_crlv(texto, nome_arquivo=nome)
    qualidade = avaliar_qualidade(campos)
    metodo = "regras_crlv"

    if not enable_retry or qualidade["score_confianca"] >= retry_min_score:
        return {
            "texto": texto,
            "campos": campos,
            "qualidade": qualidade,
            "metodo": metodo,
            "ocr_refinado_usado": False,
        }

    deadline = time.monotonic() + max(1, retry_timeout_seconds)
    campos_alvo = campos_para_retry(qualidade)

    try:
        resultado_regioes = tentar_ocr_refinado(
            arquivo=arquivo,
            nome=nome,
            texto_base=texto,
            campos_base=campos,
            qualidade_base=qualidade,
            idioma=idioma,
            max_pages=max_pages,
            timeout_seconds=min(4, retry_timeout_seconds),
            campos_alvo=campos_alvo,
            somente_regioes=True,
            metodo="regras_crlv+ocr_regioes",
        )
    except Exception as exc:
        return resultado_parcial(
            texto=texto,
            campos=campos,
            qualidade=qualidade,
            metodo=metodo,
            motivo=f"ocr_regioes_falhou: {exc}",
        )

    melhor = resultado_regioes or {
        "texto": texto,
        "campos": campos,
        "qualidade": qualidade,
        "metodo": metodo,
        "ocr_refinado_usado": True,
        "aviso": "ocr_regioes_sem_texto",
    }
    if melhor["qualidade"]["score_confianca"] >= retry_min_score:
        return melhor

    tempo_restante = int(deadline - time.monotonic())
    if tempo_restante <= 0:
        return melhor

    try:
        resultado_completo = tentar_ocr_refinado(
            arquivo=arquivo,
            nome=nome,
            texto_base=melhor["texto"],
            campos_base=melhor["campos"],
            qualidade_base=melhor["qualidade"],
            idioma=idioma,
            max_pages=max_pages,
            timeout_seconds=tempo_restante,
            campos_alvo=campos_para_retry(melhor["qualidade"]),
            somente_regioes=False,
            metodo="regras_crlv+ocr_refinado",
        )
    except Exception as exc:
        return resultado_parcial(
            texto=melhor["texto"],
            campos=melhor["campos"],
            qualidade=melhor["qualidade"],
            metodo=melhor["metodo"],
            motivo=f"ocr_refinado_falhou: {exc}",
        )

    if resultado_completo:
        return resultado_completo

    if melhor["texto"] == texto:
        return {
            "texto": texto,
            "campos": campos,
            "qualidade": qualidade,
            "metodo": metodo,
            "ocr_refinado_usado": True,
            "aviso": "ocr_refinado_sem_texto",
        }

    return melhor


def tentar_ocr_refinado(
    arquivo: Path,
    nome: str,
    texto_base: str,
    campos_base: dict[str, Any],
    qualidade_base: dict[str, Any],
    idioma: str,
    max_pages: int | None,
    timeout_seconds: int,
    campos_alvo: list[str],
    somente_regioes: bool,
    metodo: str,
) -> dict[str, Any] | None:
    texto_refinado = extrair_texto_documento_refinado(
        arquivo,
        idioma=idioma,
        max_pages=max_pages,
        timeout_seconds=timeout_seconds,
        campos_alvo=campos_alvo,
        somente_regioes=somente_regioes,
    )
    if not texto_refinado.strip():
        return None

    texto_combinado = f"{texto_base}\n\n--- OCR REFINADO BAIXA CONFIANCA ---\n{texto_refinado}"
    campos_refinados = extrair_crlv(texto_combinado, nome_arquivo=nome)
    qualidade_refinada = avaliar_qualidade(campos_refinados)

    if qualidade_refinada["score_confianca"] >= qualidade_base["score_confianca"]:
        return {
            "texto": texto_combinado,
            "campos": campos_refinados,
            "qualidade": qualidade_refinada,
            "metodo": metodo,
            "ocr_refinado_usado": True,
        }

    campos_mesclados = mesclar_campos(campos_base, campos_refinados)
    qualidade_mesclada = avaliar_qualidade(campos_mesclados)
    if qualidade_mesclada["score_confianca"] > qualidade_base["score_confianca"]:
        return {
            "texto": texto_combinado,
            "campos": campos_mesclados,
            "qualidade": qualidade_mesclada,
            "metodo": metodo,
            "ocr_refinado_usado": True,
        }

    return None


def campos_para_retry(qualidade: dict[str, Any]) -> list[str]:
    campos = []
    for chave in ("campos_faltantes_obrigatorios", "campos_faltantes_importantes", "campos_faltantes_complementares"):
        campos.extend(qualidade.get(chave) or [])
    campos.extend(item.get("campo") for item in qualidade.get("campos_suspeitos") or [] if item.get("campo"))
    return list(dict.fromkeys(campos))


def resultado_sem_melhoria(
    texto_combinado: str,
    campos: dict[str, Any],
    qualidade: dict[str, Any],
    metodo: str,
) -> dict[str, Any]:
    return {
        "texto": texto_combinado,
        "campos": campos,
        "qualidade": qualidade,
        "metodo": metodo,
        "ocr_refinado_usado": True,
        "aviso": "ocr_refinado_sem_melhoria",
    }


def resultado_parcial(
    texto: str,
    campos: dict[str, Any],
    qualidade: dict[str, Any],
    metodo: str,
    motivo: str,
) -> dict[str, Any]:
    return {
        "texto": texto,
        "campos": campos,
        "qualidade": qualidade,
        "metodo": metodo,
        "ocr_refinado_usado": True,
        "aviso": motivo,
    }


def mesclar_campos(campos_base: dict[str, Any], campos_novos: dict[str, Any]) -> dict[str, Any]:
    mesclados = dict(campos_base)
    for campo, valor in campos_novos.items():
        if not mesclados.get(campo) and valor:
            mesclados[campo] = valor
    return mesclados
