from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from src.agente import revisar_campos_crlv_com_ollama
from src.config import get_settings
from src.crlv_extrator import CRLV_FIELDS
from src.ocr import SUPPORTED_EXTENSIONS
from src.pipeline_crlv import extrair_crlv_com_retry_ocr
from src.qualidade import avaliar_qualidade
from src.schemas import ExtracaoResponse, HealthResponse


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Extrai dados estruturados de CRLV a partir de PDF/imagem.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return {"status": "ok"}


@app.post("/api/crlv/extrair", response_model=ExtracaoResponse)
async def extrair_crlv_upload(
    arquivo: UploadFile = File(...),
    usar_ollama: bool = False,
    score_minimo_ollama: int | None = None,
    modelo_ollama: str | None = None,
) -> ExtracaoResponse:
    nome_arquivo = arquivo.filename or "documento"
    extensao = Path(nome_arquivo).suffix.lower()
    if extensao not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo nao suportado. Use: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    with TemporaryDirectory() as temp_dir:
        caminho = Path(temp_dir) / nome_arquivo
        conteudo = await arquivo.read()
        caminho.write_bytes(conteudo)

        try:
            resultado = extrair_crlv_com_retry_ocr(
                arquivo=caminho,
                nome_arquivo=nome_arquivo,
                max_pages=settings.max_pages,
                retry_min_score=settings.retry_min_score,
                retry_timeout_seconds=settings.ocr_retry_timeout_seconds,
                enable_retry=settings.enable_ocr_retry,
            )
            texto = resultado["texto"]
            campos = resultado["campos"]
            qualidade = resultado["qualidade"]
            metodo = resultado["metodo"]
            score_minimo = score_minimo_ollama if score_minimo_ollama is not None else settings.review_min_score
            modelo = modelo_ollama or settings.default_ollama_model

            if usar_ollama and qualidade["score_confianca"] < score_minimo:
                campos_ollama = revisar_campos_crlv_com_ollama(
                    texto=texto,
                    campos_extraidos=campos,
                    fields=CRLV_FIELDS,
                    model=modelo,
                    ollama_url=settings.ollama_url,
                )
                campos.update({chave: valor for chave, valor in campos_ollama.items() if valor})
                qualidade = avaliar_qualidade(campos)
                metodo = "regras_crlv+revisao_ollama"

            return ExtracaoResponse.model_validate({
                "arquivo": nome_arquivo,
                "status": "ok",
                "score_confianca": qualidade["score_confianca"],
                "metodo": metodo,
                "campos": campos,
            })
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
