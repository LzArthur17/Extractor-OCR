from __future__ import annotations

from pathlib import Path
import re
from shutil import copy2
from typing import Any


CAMPOS_OBRIGATORIOS = [
    "placa",
    "renavam",
    "chassi",
    "exercicio",
    "ano_fabricacao",
    "ano_modelo",
    "marca_modelo",
    "proprietario",
    "cpf_cnpj",
    "municipio",
    "uf",
]

CAMPOS_IMPORTANTES = [
    "codigo_crv",
    "codigo_seguranca_cla",
    "motor",
    "cor",
    "combustivel",
    "categoria",
    "especie_tipo",
    "data_emissao",
]

CAMPOS_COMPLEMENTARES = [
    "capacidade",
    "potencia_cilindrada",
    "peso_bruto_total",
    "cmt",
    "eixos",
    "lotacao",
    "carroceria",
    "placa_anterior_uf",
    "observacoes",
]


def avaliar_qualidade(campos: dict[str, Any]) -> dict[str, Any]:
    faltantes_obrigatorios = _faltantes(campos, CAMPOS_OBRIGATORIOS)
    faltantes_importantes = _faltantes(campos, CAMPOS_IMPORTANTES)
    faltantes_complementares = _faltantes(campos, CAMPOS_COMPLEMENTARES)
    campos_suspeitos = validar_campos_suspeitos(campos)

    total_pontos = (
        len(CAMPOS_OBRIGATORIOS) * 3
        + len(CAMPOS_IMPORTANTES) * 2
        + len(CAMPOS_COMPLEMENTARES)
    )
    pontos = (
        (len(CAMPOS_OBRIGATORIOS) - len(faltantes_obrigatorios)) * 3
        + (len(CAMPOS_IMPORTANTES) - len(faltantes_importantes)) * 2
        + (len(CAMPOS_COMPLEMENTARES) - len(faltantes_complementares))
    )
    pontos = max(0, pontos - sum(item["penalidade"] for item in campos_suspeitos))
    score = round((pontos / total_pontos) * 100) if total_pontos else 0

    suspeitos_graves = [item for item in campos_suspeitos if item["severidade"] == "alta"]

    if faltantes_obrigatorios or suspeitos_graves:
        status_qualidade = "revisar"
    elif score < 85 or campos_suspeitos:
        status_qualidade = "conferir"
    else:
        status_qualidade = "aprovado"

    return {
        "score_confianca": score,
        "status_qualidade": status_qualidade,
        "campos_faltantes": faltantes_obrigatorios + faltantes_importantes + faltantes_complementares,
        "campos_faltantes_obrigatorios": faltantes_obrigatorios,
        "campos_faltantes_importantes": faltantes_importantes,
        "campos_faltantes_complementares": faltantes_complementares,
        "campos_suspeitos": campos_suspeitos,
    }


def separar_para_revisao(resultados: list[dict[str, Any]], input_dir: Path, saida_dir: Path) -> int:
    revisar_dir = saida_dir / "revisar"
    revisar_dir.mkdir(parents=True, exist_ok=True)
    for arquivo_antigo in revisar_dir.iterdir():
        if arquivo_antigo.is_file():
            arquivo_antigo.unlink()

    total = 0

    for item in resultados:
        if item.get("status") != "ok":
            precisa_revisao = True
        else:
            precisa_revisao = (item.get("score_confianca") or 0) < 85

        if not precisa_revisao:
            continue

        origem = input_dir / item.get("arquivo", "")
        if origem.exists():
            copy2(origem, revisar_dir / origem.name)
            total += 1

    return total


def _faltantes(campos: dict[str, Any], nomes: list[str]) -> list[str]:
    return [nome for nome in nomes if not campos.get(nome)]


def validar_campos_suspeitos(campos: dict[str, Any]) -> list[dict[str, Any]]:
    suspeitos: list[dict[str, Any]] = []

    placa = campos.get("placa")
    if placa and not re.fullmatch(r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}", placa):
        suspeitos.append(_suspeito("placa", placa, "Formato de placa invalido.", "alta", 8))

    renavam = campos.get("renavam")
    if renavam and not re.fullmatch(r"\d{9,11}", renavam):
        suspeitos.append(_suspeito("renavam", renavam, "RENAVAM deve ter de 9 a 11 digitos.", "alta", 8))

    chassi = campos.get("chassi")
    if chassi and not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", chassi):
        suspeitos.append(_suspeito("chassi", chassi, "Chassi deve ter 17 caracteres e nao usar I, O ou Q.", "alta", 8))

    cpf_cnpj = campos.get("cpf_cnpj")
    if cpf_cnpj and not documento_valido(cpf_cnpj):
        suspeitos.append(_suspeito("cpf_cnpj", cpf_cnpj, "CPF/CNPJ falhou no digito verificador.", "alta", 8))

    ano_fab = _int_ano(campos.get("ano_fabricacao"))
    ano_modelo = _int_ano(campos.get("ano_modelo"))
    exercicio = _int_ano(campos.get("exercicio"))
    if ano_fab and ano_modelo and ano_modelo < ano_fab:
        suspeitos.append(_suspeito("ano_modelo", campos.get("ano_modelo"), "Ano modelo menor que ano de fabricacao.", "alta", 6))
    if exercicio and ano_modelo and exercicio < ano_modelo - 1:
        suspeitos.append(_suspeito("exercicio", campos.get("exercicio"), "Exercicio muito menor que ano modelo.", "media", 4))

    modelo = campos.get("marca_modelo")
    if modelo and re.search(r"DPVAT|SEGUR|ASSINADO|REPASSE|PADOS|DADOS", modelo):
        suspeitos.append(_suspeito("marca_modelo", modelo, "Modelo contem texto de outro bloco do documento.", "media", 4))
    if modelo and re.search(r"\b(RERE|R0R|RERE)\b", modelo):
        suspeitos.append(_suspeito("marca_modelo", modelo, "Modelo parece conter erro de OCR.", "media", 4))

    proprietario = campos.get("proprietario")
    if proprietario and re.search(r"NUMERO|CARROCERIA|NOWE|CPF|CNPJ|SEGURAN", proprietario):
        suspeitos.append(_suspeito("proprietario", proprietario, "Proprietario parece ser linha de label/ruido de OCR.", "media", 4))

    municipio = campos.get("municipio")
    if municipio and re.search(r"\d|WEE|LOCAL|DATA", municipio):
        suspeitos.append(_suspeito("municipio", municipio, "Municipio contem numero ou ruido de OCR.", "media", 4))

    return suspeitos


def _suspeito(campo: str, valor: Any, motivo: str, severidade: str, penalidade: int) -> dict[str, Any]:
    return {
        "campo": campo,
        "valor": valor,
        "motivo": motivo,
        "severidade": severidade,
        "penalidade": penalidade,
    }


def _int_ano(valor: Any) -> int | None:
    if not valor:
        return None
    match = re.search(r"(?:19|20)\d{2}", str(valor))
    return int(match.group(0)) if match else None


def documento_valido(valor: str) -> bool:
    digitos = re.sub(r"\D", "", valor)
    if len(digitos) == 11:
        return cpf_valido(digitos)
    if len(digitos) == 14:
        return cnpj_valido(digitos)
    return False


def cpf_valido(digitos: str) -> bool:
    if len(set(digitos)) == 1:
        return False
    soma = sum(int(digitos[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10) % 11
    d1 = 0 if d1 == 10 else d1
    soma = sum(int(digitos[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10) % 11
    d2 = 0 if d2 == 10 else d2
    return digitos[-2:] == f"{d1}{d2}"


def cnpj_valido(digitos: str) -> bool:
    if len(set(digitos)) == 1:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(digitos[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto
    soma = sum(int(digitos[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto
    return digitos[-2:] == f"{d1}{d2}"
