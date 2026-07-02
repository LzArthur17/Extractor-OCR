from __future__ import annotations

from pathlib import Path

import cv2
import fitz
import numpy as np
import pdfplumber
import pytesseract
from pytesseract import TesseractError
from PIL import Image, ImageEnhance, ImageOps


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def extrair_texto_documento(path: Path, idioma: str = "por", max_pages: int | None = None) -> str:
    """Extrai texto de PDF/imagem sem interpretar o conteudo."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        texto_pdf = extrair_texto_pdf(path, max_pages=max_pages)
        if texto_pdf.strip():
            return texto_pdf
        return ocr_pdf(path, idioma=idioma, max_pages=max_pages)

    if suffix in SUPPORTED_EXTENSIONS:
        return ocr_imagem(path, idioma=idioma)

    raise ValueError(f"Tipo de arquivo nao suportado: {path.name}")


def extrair_texto_pdf(path: Path, max_pages: int | None = None) -> str:
    texto_fit = extrair_texto_pdf_pymupdf(path, max_pages=max_pages)
    if texto_fit.strip():
        return texto_fit

    partes: list[str] = []
    with pdfplumber.open(path) as pdf:
        paginas = pdf.pages[:max_pages] if max_pages else pdf.pages
        for indice, pagina in enumerate(paginas, start=1):
            texto = pagina.extract_text() or ""
            if texto.strip():
                partes.append(f"\n--- PAGINA {indice} ---\n{texto}")
    return "\n".join(partes).strip()


def extrair_texto_pdf_pymupdf(path: Path, max_pages: int | None = None) -> str:
    partes: list[str] = []
    documento = fitz.open(path)
    try:
        total_paginas = min(len(documento), max_pages) if max_pages else len(documento)
        for indice in range(total_paginas):
            texto = documento[indice].get_text("text") or ""
            if texto.strip():
                partes.append(f"\n--- PAGINA {indice + 1} ---\n{texto}")
    finally:
        documento.close()
    return "\n".join(partes).strip()


def ocr_pdf(path: Path, idioma: str = "por", dpi: int = 300, max_pages: int | None = None) -> str:
    partes: list[str] = []
    documento = fitz.open(path)
    try:
        total_paginas = min(len(documento), max_pages) if max_pages else len(documento)
        for indice in range(total_paginas):
            pagina = documento[indice]
            pixmap = pagina.get_pixmap(dpi=dpi)
            imagem = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            texto = executar_tesseract(imagem.convert("L"), idioma=idioma)

            pixmap_baixo = pagina.get_pixmap(dpi=180)
            imagem_baixa = Image.frombytes("RGB", [pixmap_baixo.width, pixmap_baixo.height], pixmap_baixo.samples)
            texto_baixo = executar_tesseract(imagem_baixa, idioma=idioma)

            partes.append(f"\n--- PAGINA {indice + 1} OCR 300 ---\n{texto}")
            partes.append(f"\n--- PAGINA {indice + 1} OCR 180 ---\n{texto_baixo}")
            partes.append(ocr_regioes_crlv(imagem, idioma=idioma, pagina=indice + 1))
    finally:
        documento.close()
    return "\n".join(partes).strip()


def ocr_imagem(path: Path, idioma: str = "por") -> str:
    with Image.open(path) as imagem:
        return executar_tesseract(imagem, idioma=idioma).strip()


def executar_tesseract(imagem: Image.Image, idioma: str = "por") -> str:
    config = "--psm 6"
    try:
        return pytesseract.image_to_string(imagem, lang=idioma, config=config)
    except TesseractError as exc:
        if idioma != "eng" and "Failed loading language" in str(exc):
            return pytesseract.image_to_string(imagem, lang="eng", config=config)
        raise


def executar_tesseract_linha(imagem: Image.Image, idioma: str = "por") -> str:
    config = "--psm 7"
    try:
        return pytesseract.image_to_string(imagem, lang=idioma, config=config)
    except TesseractError as exc:
        if idioma != "eng" and "Failed loading language" in str(exc):
            return pytesseract.image_to_string(imagem, lang="eng", config=config)
        raise


def ocr_regioes_crlv(imagem: Image.Image, idioma: str, pagina: int) -> str:
    imagem_corrigida = corrigir_perspectiva_documento(imagem)
    regioes = {
        "renavam": (0.04, 0.13, 0.28, 0.18),
        "placa_exercicio": (0.04, 0.18, 0.28, 0.25),
        "ano_fabricacao_modelo": (0.04, 0.24, 0.28, 0.31),
        "codigo_crv": (0.04, 0.31, 0.28, 0.37),
        "codigo_seguranca_cla": (0.04, 0.43, 0.32, 0.50),
        "marca_modelo": (0.04, 0.50, 0.50, 0.58),
        "especie_tipo": (0.04, 0.57, 0.50, 0.65),
        "placa_anterior_chassi": (0.04, 0.64, 0.50, 0.72),
        "cor_combustivel": (0.04, 0.71, 0.50, 0.78),
        "categoria_capacidade": (0.54, 0.12, 0.96, 0.19),
        "potencia_pbt": (0.54, 0.19, 0.96, 0.25),
        "motor_cmt_eixos_lotacao": (0.54, 0.24, 0.96, 0.31),
        "carroceria": (0.54, 0.30, 0.96, 0.36),
        "proprietario": (0.54, 0.35, 0.96, 0.44),
        "cpf_cnpj": (0.76, 0.41, 0.96, 0.49),
        "local_data": (0.54, 0.47, 0.96, 0.54),
        "observacoes": (0.04, 0.78, 0.50, 0.89),
    }

    partes = [f"\n--- PAGINA {pagina} OCR REGIOES CRLV ---"]
    for nome, caixa in regioes.items():
        recorte = recortar_normalizado(imagem_corrigida, caixa)
        texto = executar_tesseract_linha(preparar_recorte_para_ocr(recorte), idioma=idioma).strip()
        if texto:
            partes.append(f"[REGIAO {nome}] {texto}")
    return "\n".join(partes)


def recortar_normalizado(imagem: Image.Image, caixa: tuple[float, float, float, float]) -> Image.Image:
    largura, altura = imagem.size
    esquerda, topo, direita, baixo = caixa
    return imagem.crop((
        int(largura * esquerda),
        int(altura * topo),
        int(largura * direita),
        int(altura * baixo),
    ))


def preparar_recorte_para_ocr(imagem: Image.Image) -> Image.Image:
    cinza = ImageOps.grayscale(imagem)
    cinza = ImageEnhance.Contrast(cinza).enhance(2.0)
    largura, altura = cinza.size
    escala = max(1, 900 // max(1, largura))
    if escala > 1:
        cinza = cinza.resize((largura * escala, altura * escala), Image.Resampling.LANCZOS)
    return cinza


def corrigir_perspectiva_documento(imagem: Image.Image) -> Image.Image:
    array = np.array(imagem.convert("RGB"))
    cinza = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(cinza, (5, 5), 0)
    bordas = cv2.Canny(blur, 40, 120)
    contornos, _ = cv2.findContours(bordas, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return imagem

    contornos = sorted(contornos, key=cv2.contourArea, reverse=True)[:8]
    for contorno in contornos:
        perimetro = cv2.arcLength(contorno, True)
        aproximado = cv2.approxPolyDP(contorno, 0.02 * perimetro, True)
        area = cv2.contourArea(aproximado)
        if len(aproximado) == 4 and area > array.shape[0] * array.shape[1] * 0.20:
            pontos = ordenar_pontos(aproximado.reshape(4, 2).astype("float32"))
            destino = np.array(
                [[0, 0], [1200, 0], [1200, 1800], [0, 1800]],
                dtype="float32",
            )
            matriz = cv2.getPerspectiveTransform(pontos, destino)
            corrigida = cv2.warpPerspective(array, matriz, (1200, 1800))
            return Image.fromarray(corrigida)
    return imagem


def ordenar_pontos(pontos: np.ndarray) -> np.ndarray:
    soma = pontos.sum(axis=1)
    diff = np.diff(pontos, axis=1)
    ordenados = np.zeros((4, 2), dtype="float32")
    ordenados[0] = pontos[np.argmin(soma)]
    ordenados[2] = pontos[np.argmax(soma)]
    ordenados[1] = pontos[np.argmin(diff)]
    ordenados[3] = pontos[np.argmax(diff)]
    return ordenados
