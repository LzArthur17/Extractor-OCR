from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from src.agente import revisar_campos_crlv_com_ollama
from src.crlv_extrator import CRLV_FIELDS, extrair_crlv
from src.mapeamento_formulario import montar_campos_formulario
from src.ocr import SUPPORTED_EXTENSIONS, extrair_texto_documento
from src.qualidade import avaliar_qualidade


app = FastAPI(
    title="API Extrator CRLV",
    version="1.0.0",
    description="Extrai dados estruturados de CRLV a partir de PDF/imagem.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/crlv/extrair")
async def extrair_crlv_upload(
    arquivo: UploadFile = File(...),
    usar_ollama: bool = False,
    score_minimo_ollama: int = 90,
    modelo_ollama: str = "llama3.1",
) -> dict[str, Any]:
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
            texto = extrair_texto_documento(caminho, max_pages=1)
            campos = extrair_crlv(texto, nome_arquivo=nome_arquivo)
            qualidade = avaliar_qualidade(campos)
            metodo = "regras_crlv"

            if usar_ollama and qualidade["score_confianca"] < score_minimo_ollama:
                campos_ollama = revisar_campos_crlv_com_ollama(
                    texto=texto,
                    campos_extraidos=campos,
                    fields=CRLV_FIELDS,
                    model=modelo_ollama,
                )
                campos.update({chave: valor for chave, valor in campos_ollama.items() if valor})
                qualidade = avaliar_qualidade(campos)
                metodo = "regras_crlv+revisao_ollama"

            return {
                "arquivo": nome_arquivo,
                "status": "ok",
                "score_confianca": qualidade["score_confianca"],
                "metodo": metodo,
                "campos_formulario": montar_campos_formulario(campos),
                "campos": campos,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
