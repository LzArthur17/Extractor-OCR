from __future__ import annotations

import time
from pathlib import Path

import cv2
import fitz
import numpy as np
import pdfplumber
import pytesseract
from pytesseract import TesseractError
from PIL import Image, ImageEnhance, ImageOps


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

REGIOES_POR_CAMPO = {
    "renavam": {"renavam"},
    "placa": {"placa_exercicio"},
    "exercicio": {"placa_exercicio"},
    "ano_fabricacao": {"ano_fabricacao_modelo"},
    "ano_modelo": {"ano_fabricacao_modelo"},
    "codigo_crv": {"codigo_crv"},
    "codigo_seguranca_cla": {"codigo_seguranca_cla"},
    "marca_modelo": {"marca_modelo"},
    "especie_tipo": {"especie_tipo"},
    "placa_anterior_uf": {"placa_anterior_chassi"},
    "chassi": {"placa_anterior_chassi"},
    "cor": {"cor_combustivel"},
    "combustivel": {"cor_combustivel"},
    "categoria": {"categoria_capacidade"},
    "capacidade": {"categoria_capacidade"},
    "potencia_cilindrada": {"potencia_pbt"},
    "peso_bruto_total": {"potencia_pbt"},
    "motor": {"motor_cmt_eixos_lotacao"},
    "cmt": {"motor_cmt_eixos_lotacao"},
    "eixos": {"motor_cmt_eixos_lotacao"},
    "lotacao": {"motor_cmt_eixos_lotacao"},
    "carroceria": {"carroceria"},
    "proprietario": {"proprietario"},
    "cpf_cnpj": {"cpf_cnpj"},
    "municipio": {"local_data"},
    "uf": {"local_data"},
    "data_emissao": {"local_data"},
    "observacoes": {"observacoes"},
}


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


def extrair_texto_documento_refinado(
    path: Path,
    idioma: str = "por",
    max_pages: int | None = None,
    timeout_seconds: int = 12,
    campos_alvo: list[str] | None = None,
    somente_regioes: bool = False,
) -> str:
    """Executa OCR mais agressivo para documentos com baixa confianca."""
    deadline = time.monotonic() + max(1, timeout_seconds)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return ocr_pdf_refinado(
            path,
            idioma=idioma,
            max_pages=max_pages,
            deadline=deadline,
            campos_alvo=campos_alvo,
            somente_regioes=somente_regioes,
        )

    if suffix in SUPPORTED_EXTENSIONS:
        with Image.open(path) as imagem:
            return ocr_imagem_refinado(
                imagem,
                idioma=idioma,
                deadline=deadline,
                campos_alvo=campos_alvo,
                somente_regioes=somente_regioes,
            )

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


def ocr_pdf_refinado(
    path: Path,
    idioma: str,
    max_pages: int | None,
    deadline: float,
    campos_alvo: list[str] | None = None,
    somente_regioes: bool = False,
) -> str:
    partes: list[str] = []
    documento = fitz.open(path)
    try:
        total_paginas = min(len(documento), max_pages) if max_pages else len(documento)
        for indice in range(total_paginas):
            if tempo_esgotado(deadline):
                break
            pagina = documento[indice]
            pixmap = pagina.get_pixmap(dpi=420)
            imagem = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            partes.append(f"\n--- PAGINA {indice + 1} OCR REFINADO ---")
            texto = ocr_imagem_refinado(
                imagem,
                idioma=idioma,
                deadline=deadline,
                campos_alvo=campos_alvo,
                somente_regioes=somente_regioes,
            )
            if texto:
                partes.append(texto)
    finally:
        documento.close()
    return "\n".join(partes).strip()


def ocr_imagem_refinado(
    imagem: Image.Image,
    idioma: str,
    deadline: float,
    campos_alvo: list[str] | None = None,
    somente_regioes: bool = False,
) -> str:
    partes: list[str] = []
    imagem_corrigida = corrigir_perspectiva_documento(imagem)
    regioes_alvo = regioes_para_campos(campos_alvo)

    if somente_regioes:
        return ocr_regioes_crlv(
            imagem_corrigida,
            idioma=idioma,
            pagina=1,
            deadline=deadline,
            regioes_alvo=regioes_alvo,
        ).strip()

    variantes = preparar_variantes_refinadas(imagem_corrigida)

    for nome, variante in variantes:
        if tempo_esgotado(deadline):
            break
        texto = executar_tesseract(
            variante,
            idioma=idioma,
            config="--psm 6",
            timeout_seconds=tempo_restante(deadline),
        ).strip()
        if texto:
            partes.append(f"[OCR REFINADO {nome}]\n{texto}")

    if not tempo_esgotado(deadline):
        texto = executar_tesseract(
            variantes[0][1],
            idioma=idioma,
            config="--psm 11",
            timeout_seconds=tempo_restante(deadline),
        ).strip()
        if texto:
            partes.append(f"[OCR REFINADO TEXTO ESPARSO]\n{texto}")

    if not tempo_esgotado(deadline):
        partes.append(
            ocr_regioes_crlv(
                imagem_corrigida,
                idioma=idioma,
                pagina=1,
                deadline=deadline,
                regioes_alvo=regioes_alvo,
            )
        )

    return "\n".join(parte for parte in partes if parte).strip()


def preparar_variantes_refinadas(imagem: Image.Image) -> list[tuple[str, Image.Image]]:
    cinza = ImageOps.grayscale(imagem)
    cinza = ImageEnhance.Contrast(cinza).enhance(2.4)
    cinza = aumentar_imagem(cinza, largura_minima=1800)

    array = np.array(cinza)
    denoise = cv2.fastNlMeansDenoising(array, None, 12, 7, 21)
    adaptativa = cv2.adaptiveThreshold(
        denoise,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    _, otsu = cv2.threshold(denoise, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    nitida = cv2.filter2D(denoise, -1, kernel)

    return [
        ("contraste", cinza),
        ("adaptativo", Image.fromarray(adaptativa)),
        ("otsu", Image.fromarray(otsu)),
        ("nitidez", Image.fromarray(nitida)),
    ]


def aumentar_imagem(imagem: Image.Image, largura_minima: int) -> Image.Image:
    largura, altura = imagem.size
    if largura >= largura_minima:
        return imagem
    escala = largura_minima / max(1, largura)
    return imagem.resize((int(largura * escala), int(altura * escala)), Image.Resampling.LANCZOS)


def executar_tesseract(
    imagem: Image.Image,
    idioma: str = "por",
    config: str = "--psm 6",
    timeout_seconds: float | None = None,
) -> str:
    try:
        return pytesseract.image_to_string(imagem, lang=idioma, config=config, timeout=timeout_seconds)
    except TesseractError as exc:
        if idioma != "eng" and "Failed loading language" in str(exc):
            return pytesseract.image_to_string(imagem, lang="eng", config=config, timeout=timeout_seconds)
        raise
    except RuntimeError:
        return ""


def executar_tesseract_linha(
    imagem: Image.Image,
    idioma: str = "por",
    timeout_seconds: float | None = None,
) -> str:
    config = "--psm 7"
    try:
        return pytesseract.image_to_string(imagem, lang=idioma, config=config, timeout=timeout_seconds)
    except TesseractError as exc:
        if idioma != "eng" and "Failed loading language" in str(exc):
            return pytesseract.image_to_string(imagem, lang="eng", config=config, timeout=timeout_seconds)
        raise
    except RuntimeError:
        return ""


def ocr_regioes_crlv(
    imagem: Image.Image,
    idioma: str,
    pagina: int,
    deadline: float | None = None,
    regioes_alvo: set[str] | None = None,
) -> str:
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
    if regioes_alvo:
        regioes = {nome: caixa for nome, caixa in regioes.items() if nome in regioes_alvo}

    partes = [f"\n--- PAGINA {pagina} OCR REGIOES CRLV ---"]
    for nome, caixa in regioes.items():
        if deadline is not None and tempo_esgotado(deadline):
            break
        recorte = recortar_normalizado(imagem_corrigida, caixa)
        texto = executar_tesseract_linha(
            preparar_recorte_para_ocr(recorte),
            idioma=idioma,
            timeout_seconds=tempo_restante(deadline) if deadline is not None else None,
        ).strip()
        if texto:
            partes.append(f"[REGIAO {nome}] {texto}")
    return "\n".join(partes)


def regioes_para_campos(campos: list[str] | None) -> set[str] | None:
    if not campos:
        return None
    regioes: set[str] = set()
    for campo in campos:
        regioes.update(REGIOES_POR_CAMPO.get(campo, set()))
    return regioes or None


def tempo_esgotado(deadline: float) -> bool:
    return time.monotonic() >= deadline


def tempo_restante(deadline: float) -> float:
    return max(0.5, deadline - time.monotonic())


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
