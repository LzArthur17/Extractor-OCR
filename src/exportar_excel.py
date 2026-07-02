from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Any

import pandas as pd


def salvar_resultados(resultados: list[dict[str, Any]], saida_dir: Path) -> None:
    saida_dir.mkdir(parents=True, exist_ok=True)
    json_path = saida_dir / "resultados.json"
    excel_path = saida_dir / "resultados.xlsx"

    resultados_publicos = [limpar_resultado_publico(item) for item in resultados]
    json_path.write_text(
        json.dumps(resultados_publicos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    linhas = []
    for item in resultados_publicos:
        linha = {
            "arquivo": item.get("arquivo"),
            "status": item.get("status"),
            "score_confianca": item.get("score_confianca"),
            "metodo": item.get("metodo"),
            "erro": item.get("erro"),
        }
        campos = item.get("campos") or {}
        linha.update(campos)
        linhas.append(linha)

    dataframe = pd.DataFrame(linhas)
    try:
        dataframe.to_excel(excel_path, index=False)
    except PermissionError:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fallback_path = saida_dir / f"resultados_{timestamp}.xlsx"
        dataframe.to_excel(fallback_path, index=False)
        print(f"Arquivo Excel bloqueado. Salvei a copia em: {fallback_path}")


def limpar_resultado_publico(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "arquivo": item.get("arquivo"),
        "status": item.get("status"),
        "score_confianca": item.get("score_confianca"),
        "metodo": item.get("metodo"),
        "erro": item.get("erro"),
        "campos": item.get("campos") or {},
    }
