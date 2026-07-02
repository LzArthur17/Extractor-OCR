from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from src.agente import extrair_campos_com_ollama, revisar_campos_crlv_com_ollama
from src.crlv_extrator import CRLV_FIELDS, extrair_crlv, score_crlv
from src.exportar_excel import salvar_resultados
from src.ocr import SUPPORTED_EXTENSIONS, extrair_texto_documento
from src.qualidade import avaliar_qualidade, separar_para_revisao


ROOT = Path(__file__).resolve().parents[1]
ENTRADA_DIR = ROOT / "documentos_entrada"
SAIDA_DIR = ROOT / "saida"
TEXTOS_DIR = SAIDA_DIR / "textos_ocr"


def main() -> None:
    args = parse_args()
    args.input_dir.mkdir(exist_ok=True)
    TEXTOS_DIR.mkdir(parents=True, exist_ok=True)

    arquivos = listar_documentos(args.input_dir)
    if not arquivos:
        print(f"Nenhum documento encontrado em: {args.input_dir}")
        print(f"Extensoes aceitas: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        return

    resultados = []
    total = len(arquivos)
    workers = min(args.workers, total)
    print(f"Processando {total} documento(s) com {workers} worker(s)...")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(processar_arquivo, arquivo, args): arquivo for arquivo in arquivos}
        for indice, future in enumerate(as_completed(futures), start=1):
            arquivo = futures[future]
            resultado = future.result()
            resultados.append(resultado)
            print(f"[{indice}/{total}] {arquivo.name}: {resultado['status']}")

    resultados.sort(key=lambda item: item["arquivo"])
    salvar_resultados(resultados, SAIDA_DIR)
    total_revisao = separar_para_revisao(resultados, args.input_dir, SAIDA_DIR)
    if total_revisao:
        print(f"Documentos para revisao copiados para: {SAIDA_DIR / 'revisar'} ({total_revisao})")
    print(f"Concluido. Resultados em: {SAIDA_DIR}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extrai informacoes de CRLVs com OCR + regras e fallback opcional por Ollama.")
    parser.add_argument("--input-dir", type=Path, default=ENTRADA_DIR, help="Pasta com documentos de entrada.")
    parser.add_argument("--model", default="llama3.1", help="Modelo do Ollama.")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="URL base do Ollama.")
    parser.add_argument("--ocr-lang", default="por", help="Idioma do OCR/Tesseract.")
    parser.add_argument("--fields", nargs="+", default=CRLV_FIELDS, help="Campos que devem retornar.")
    parser.add_argument("--document-type", choices=["crlv"], default="crlv", help="Tipo de documento processado.")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1), help="Processamentos em paralelo.")
    parser.add_argument("--max-pages", type=int, default=1, help="Quantidade maxima de paginas lidas por PDF.")
    parser.add_argument("--force-ocr", action="store_true", help="Ignora texto em cache e extrai novamente.")
    parser.add_argument("--use-ollama-fallback", action="store_true", help="Usa Ollama apenas quando a extracao por regras estiver fraca.")
    parser.add_argument("--fallback-min-score", type=int, default=3, help="Pontuacao minima da extracao por regras antes de acionar fallback.")
    parser.add_argument("--use-ollama-review", action="store_true", help="Usa Ollama para revisar documentos abaixo do score minimo.")
    parser.add_argument("--review-min-score", type=int, default=90, help="Score abaixo do qual o Ollama revisa os campos.")
    return parser.parse_args()


def listar_documentos(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def processar_arquivo(arquivo: Path, args: argparse.Namespace) -> dict[str, Any]:
    try:
        texto = obter_texto_extraido(
            arquivo=arquivo,
            idioma=args.ocr_lang,
            max_pages=args.max_pages,
            force_ocr=args.force_ocr,
        )

        campos = extrair_crlv(texto, nome_arquivo=arquivo.name)
        metodo = "regras_crlv"

        if args.use_ollama_fallback and score_crlv(campos) < args.fallback_min_score:
            campos_ollama = extrair_campos_com_ollama(
                texto=texto,
                fields=args.fields,
                model=args.model,
                ollama_url=args.ollama_url,
            )
            campos.update({chave: valor for chave, valor in campos_ollama.items() if valor})
            metodo = "regras_crlv+ollama"

        qualidade = avaliar_qualidade(campos)

        if args.use_ollama_review and qualidade["score_confianca"] < args.review_min_score:
            campos_ollama = revisar_campos_crlv_com_ollama(
                texto=texto,
                campos_extraidos=campos,
                fields=args.fields,
                model=args.model,
                ollama_url=args.ollama_url,
            )
            campos.update({chave: valor for chave, valor in campos_ollama.items() if valor})
            metodo = f"{metodo}+revisao_ollama"
            qualidade = avaliar_qualidade(campos)

        return {
            "arquivo": arquivo.name,
            "status": "ok",
            "erro": None,
            "metodo": metodo,
            **qualidade,
            "campos": campos,
        }
    except Exception as exc:
        return {
            "arquivo": arquivo.name,
            "status": "erro",
            "erro": str(exc),
            "metodo": None,
            "score_confianca": 0,
            "campos": {},
        }


def obter_texto_extraido(arquivo: Path, idioma: str, max_pages: int | None, force_ocr: bool) -> str:
    destino = caminho_texto_extraido(arquivo)
    if not force_ocr and destino.exists() and destino.stat().st_mtime >= arquivo.stat().st_mtime:
        return destino.read_text(encoding="utf-8")

    texto = extrair_texto_documento(arquivo, idioma=idioma, max_pages=max_pages)
    salvar_texto_extraido(arquivo, texto)
    return texto


def salvar_texto_extraido(arquivo: Path, texto: str) -> None:
    destino = caminho_texto_extraido(arquivo)
    destino.write_text(texto, encoding="utf-8")


def caminho_texto_extraido(arquivo: Path) -> Path:
    return TEXTOS_DIR / f"{arquivo.stem}.txt"


if __name__ == "__main__":
    main()
