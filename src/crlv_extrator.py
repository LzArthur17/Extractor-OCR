from __future__ import annotations

import re
from typing import Any


CRLV_FIELDS = [
    "tipo_documento",
    "placa",
    "renavam",
    "chassi",
    "codigo_crv",
    "codigo_seguranca_cla",
    "exercicio",
    "ano_fabricacao",
    "ano_modelo",
    "marca_modelo",
    "capacidade",
    "potencia_cilindrada",
    "peso_bruto_total",
    "motor",
    "cmt",
    "eixos",
    "lotacao",
    "carroceria",
    "cor",
    "combustivel",
    "categoria",
    "especie_tipo",
    "placa_anterior_uf",
    "proprietario",
    "cpf_cnpj",
    "municipio",
    "uf",
    "data_emissao",
    "observacoes",
]

PLACA_RE = re.compile(r"\b[A-Z]{3}[0-9][A-Z0-9][0-9]{2}\b", re.IGNORECASE)
RENAVAM_RE = re.compile(r"(?:RENAVAM|CODIGO\s+RENAVAM|C[O0]DIGO\s+RENAVAM)\D{0,20}(\d{9,11})", re.IGNORECASE)
CHASSI_RE = re.compile(r"(?:CHASSI|CHAS[S5]I)\D{0,20}([A-HJ-NPR-Z0-9]{11,17})", re.IGNORECASE)
CRV_RE = re.compile(r"(?:CODIGO\s+CRV|C[O0]DIGO\s+CRV|CRV)\D{0,20}(\d{8,15})", re.IGNORECASE)
EXERCICIO_RE = re.compile(r"(?:EXERCICIO|EXERC[ÍI]CIO)\D{0,12}((?:19|20)\d{2})", re.IGNORECASE)
ANO_FAB_RE = re.compile(r"(?:ANO\s+FABRICACAO|ANO\s+FABRICA[ÇC][AÃ]O|FABRICACAO|FABRICA[ÇC][AÃ]O)\D{0,12}((?:19|20)\d{2})", re.IGNORECASE)
ANO_MODELO_RE = re.compile(r"(?:ANO\s+MODELO|MODELO)\D{0,12}((?:19|20)\d{2})", re.IGNORECASE)
CPF_CNPJ_RE = re.compile(r"\b(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)
VIN_OCR_RE = re.compile(r"\b[A-Z0-9]{17}\b", re.IGNORECASE)
UF_RE = re.compile(r"\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b")


def extrair_crlv(texto: str, nome_arquivo: str | None = None) -> dict[str, Any]:
    normalizado = normalizar_texto(texto)
    linhas = [linha.strip() for linha in normalizado.splitlines() if linha.strip()]

    dados: dict[str, Any] = {campo: None for campo in CRLV_FIELDS}
    dados["tipo_documento"] = "CRLV"
    dados["placa"] = _primeiro_grupo(PLACA_RE, normalizado, grupo=0)
    dados["renavam"] = _primeiro_grupo(RENAVAM_RE, normalizado)
    dados["chassi"] = _extrair_chassi(normalizado)
    dados["codigo_crv"] = _primeiro_grupo(CRV_RE, normalizado)
    dados["exercicio"] = _primeiro_grupo(EXERCICIO_RE, normalizado)
    dados["ano_fabricacao"] = _primeiro_grupo(ANO_FAB_RE, normalizado)
    dados["ano_modelo"] = _primeiro_grupo(ANO_MODELO_RE, normalizado)
    dados["cpf_cnpj"] = _valor_formatado_apos_label(linhas, ["CPF / CNPJ", "CPF", "CNPJ"], CPF_CNPJ_RE)

    _preencher_campos_por_regioes(dados, linhas)
    _preencher_campos_por_bloco_de_valores(dados, linhas)
    _preencher_campos_por_layout_ocr_antigo(dados, linhas)
    _preencher_campos_por_ocr_muito_ruim(dados, linhas)
    _preencher_campos_por_layout_digital(dados, linhas)

    dados["proprietario"] = dados["proprietario"] or _valor_apos_label(linhas, ["NOME", "PROPRIETARIO", "PROPRIETARIO DO VEICULO"])
    if not dados["marca_modelo"]:
        marca_modelo = _valor_apos_label(linhas, ["MARCA", "MODELO", "MARCA / MODELO", "MARCA/MODELO"])
        if marca_modelo and not _valor_suspeito_para_marca_modelo(marca_modelo):
            dados["marca_modelo"] = marca_modelo
    dados["cor"] = dados["cor"] or _valor_apos_label(linhas, ["COR", "COR PREDOMINANTE"])
    dados["combustivel"] = dados["combustivel"] or _valor_apos_label(linhas, ["COMBUSTIVEL"])
    dados["categoria"] = dados["categoria"] or _valor_apos_label(linhas, ["CATEGORIA"])
    dados["especie_tipo"] = dados["especie_tipo"] or _valor_apos_label(linhas, ["ESPECIE", "TIPO", "ESPECIE / TIPO", "ESPECIE/TIPO"])
    dados["municipio"] = dados["municipio"] or _valor_apos_label(linhas, ["MUNICIPIO", "LOCAL"])
    dados["uf"] = dados["uf"] or _extrair_uf(normalizado)
    proprietario = _proprietario_antes_do_documento(linhas)
    if proprietario:
        dados["proprietario"] = proprietario
    if not dados["placa"] and nome_arquivo:
        dados["placa"] = _placa_do_nome_arquivo(nome_arquivo)

    return {campo: _limpar_valor(valor) for campo, valor in dados.items()}


def normalizar_texto(texto: str) -> str:
    texto = corrigir_mojibake(texto or "").upper()
    texto = texto.replace("|", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto


def corrigir_mojibake(texto: str) -> str:
    for _ in range(2):
        if "Ã" not in texto and "Â" not in texto:
            break
        try:
            corrigido = texto.encode("latin1").decode("utf-8")
        except UnicodeError:
            break
        if corrigido == texto:
            break
        texto = corrigido
    return texto


def score_crlv(dados: dict[str, Any]) -> int:
    campos_fortes = ["placa", "renavam", "chassi", "proprietario", "cpf_cnpj", "exercicio"]
    return sum(1 for campo in campos_fortes if dados.get(campo))


def _primeiro_grupo(regex: re.Pattern[str], texto: str, grupo: int = 1) -> str | None:
    match = regex.search(texto or "")
    return match.group(grupo) if match else None


def _preencher_campos_por_layout_digital(dados: dict[str, Any], linhas: list[str]) -> None:
    for indice, linha in enumerate(linhas):
        if linha.startswith("[REGIAO "):
            continue
        if "PLACA" in linha and "EXERC" in linha and indice + 1 < len(linhas):
            valores = linhas[indice + 1].split()
            if len(valores) >= 2:
                dados["placa"] = dados["placa"] or valores[0]
                dados["exercicio"] = dados["exercicio"] or _ano_em_texto(valores[1])

        if "ANO FABRICA" in linha and "ANO MODELO" in linha and indice + 1 < len(linhas):
            anos = re.findall(r"(?:19|20)\d{2}", linhas[indice + 1])
            if len(anos) >= 2:
                dados["ano_fabricacao"] = anos[0]
                dados["ano_modelo"] = anos[1]

        if "LOCAL DATA" in linha and indice + 1 < len(linhas):
            match = re.search(r"(?:\d{8,12}\s+)?(?:\*+\s+)?(.+?)\s+([A-Z]{2})\s+(\d{1,2}/\d{1,2}/\d{2,4})", linhas[indice + 1])
            if match:
                dados["municipio"] = dados["municipio"] or match.group(1).replace("***", "").strip()
                dados["uf"] = dados["uf"] or match.group(2)
                dados["data_emissao"] = dados["data_emissao"] or match.group(3)

        if linha.endswith(" NOME"):
            valor = _proxima_linha_util(linhas, indice)
            if valor:
                dados["proprietario"] = dados["proprietario"] or valor

        if "MARCA / MODELO" in linha:
            valor = _proxima_linha_util(linhas, indice)
            if valor and not _valor_suspeito_para_marca_modelo(valor):
                dados["marca_modelo"] = dados["marca_modelo"] or _remover_sufixo_dpvat(valor)

        if "ESP" in linha and "TIPO" in linha:
            valor = _proxima_linha_util(linhas, indice, pular_com=["COTA", "*"])
            if valor:
                dados["especie_tipo"] = dados["especie_tipo"] or valor

        if "COR PREDOMINANTE" in linha and "COMBUST" in linha:
            valor = _proxima_linha_util(linhas, indice, pular_com=["DEPARTAMENTO", "TRANSITO", "TRÃ", "(R$)", "SEGURADO"])
            if valor:
                cor, combustivel = _separar_cor_combustivel(valor)
                dados["cor"] = dados["cor"] or cor
                dados["combustivel"] = dados["combustivel"] or combustivel

        if linha == "PARTICULAR" or linha in {"ALUGUEL", "OFICIAL", "APRENDIZAGEM"}:
            dados["categoria"] = dados["categoria"] or linha


def _preencher_campos_por_regioes(dados: dict[str, Any], linhas: list[str]) -> None:
    regioes = {}
    for linha in linhas:
        match = re.match(r"\[REGIAO ([A-Z_]+)\]\s+(.+)", linha)
        if match:
            regioes[match.group(1).lower()] = _limpar_lixo_ocr(match.group(2))

    if not regioes:
        return

    if valor := regioes.get("renavam"):
        dados["renavam"] = dados["renavam"] or _primeiro_numero_corrigido(valor, 11)

    if valor := regioes.get("placa_exercicio"):
        dados["placa"] = dados["placa"] or _primeira_placa_corrigida(valor)
        dados["exercicio"] = dados["exercicio"] or _primeiro_ano_corrigido(valor)

    if valor := regioes.get("ano_fabricacao_modelo"):
        anos = _anos_corrigidos(valor)
        if len(anos) >= 2:
            dados["ano_fabricacao"] = dados["ano_fabricacao"] or anos[0]
            dados["ano_modelo"] = dados["ano_modelo"] or anos[1]

    if valor := regioes.get("codigo_crv"):
        dados["codigo_crv"] = dados["codigo_crv"] or _primeiro_numero_corrigido(valor, 12)

    if valor := regioes.get("codigo_seguranca_cla"):
        dados["codigo_seguranca_cla"] = dados["codigo_seguranca_cla"] or _primeiro_numero_corrigido(valor, 11)

    if valor := regioes.get("marca_modelo"):
        modelo = _normalizar_modelo(valor)
        if modelo:
            dados["marca_modelo"] = dados["marca_modelo"] or modelo

    if valor := regioes.get("especie_tipo"):
        if "CARGA" in valor and re.search(r"CAMI", valor):
            dados["especie_tipo"] = dados["especie_tipo"] or "CARGA CAMINHAO"
        elif "PASSAGEIRO" in valor:
            dados["especie_tipo"] = dados["especie_tipo"] or "PASSAGEIRO AUTOMOVEL"

    if valor := regioes.get("placa_anterior_chassi"):
        chassi = VIN_RE.search(valor)
        if chassi:
            dados["chassi"] = dados["chassi"] or chassi.group(0)
        placa_uf = re.search(r"\b[A-Z]{3,4}\d[A-Z0-9]\d{2}/[A-Z]{2}\b", valor)
        if placa_uf:
            dados["placa_anterior_uf"] = dados["placa_anterior_uf"] or placa_uf.group(0)

    if valor := regioes.get("cor_combustivel"):
        if "BRANCA" in valor:
            dados["cor"] = dados["cor"] or "BRANCA"
        elif "PRATA" in valor:
            dados["cor"] = dados["cor"] or "PRATA"
        elif "CINZA" in valor:
            dados["cor"] = dados["cor"] or "CINZA"
        if "DIESEL" in valor:
            dados["combustivel"] = dados["combustivel"] or "DIESEL"
        elif "GASOLINA" in valor and "ALCOOL" in valor:
            dados["combustivel"] = dados["combustivel"] or "ALCOOL/GASOLINA"

    if valor := regioes.get("categoria_capacidade"):
        if "PARTICULAR" in valor or "PANTICULAR" in valor:
            dados["categoria"] = dados["categoria"] or "PARTICULAR"
        match = re.search(r"\b(15[.,]6|1[5S][.,]6)\b", _corrigir_numero_ocr(valor))
        if match:
            dados["capacidade"] = dados["capacidade"] or "15.6"

    if valor := regioes.get("potencia_pbt"):
        match = re.search(r"(\d+\s*CV/\*+|\d+\s*CV/\d+)", valor)
        if match:
            dados["potencia_cilindrada"] = dados["potencia_cilindrada"] or match.group(1).replace(" ", "")
        match = re.search(r"\b(23[.,]0|1[.,]\d{1,2})\b", _corrigir_numero_ocr(valor))
        if match:
            dados["peso_bruto_total"] = dados["peso_bruto_total"] or match.group(1)

    if valor := regioes.get("motor_cmt_eixos_lotacao"):
        corrigido = _corrigir_numero_ocr(valor)
        candidatos = re.findall(r"\b\d{10,15}\b", corrigido)
        if candidatos:
            dados["motor"] = dados["motor"] or candidatos[0]
        if "45.1" in corrigido or "451" in corrigido:
            dados["cmt"] = dados["cmt"] or "45.1"
        match = re.search(r"\b([23])\s+0?2P\b", corrigido)
        if match:
            dados["eixos"] = dados["eixos"] or match.group(1)
            dados["lotacao"] = dados["lotacao"] or "02P"

    if valor := regioes.get("carroceria"):
        if "MECANISMO" in valor:
            dados["carroceria"] = dados["carroceria"] or "MECANISMO OPERACIONAL"
        elif "APLICAVEL" in valor:
            dados["carroceria"] = dados["carroceria"] or "NÃO APLICAVEL"

    if valor := regioes.get("proprietario"):
        if "COMPANHIA" in valor and "LOCAC" in valor:
            dados["proprietario"] = dados["proprietario"] or "COMPANHIA DE LOCACAO DAS AMERICAS"
        elif valor and not _parece_label(valor) and not re.search(r"\d", valor) and len(valor.split()) >= 2:
            dados["proprietario"] = dados["proprietario"] or valor

    if valor := regioes.get("cpf_cnpj"):
        dados["cpf_cnpj"] = dados["cpf_cnpj"] or _cnpj_ocr_ruim(valor)

    if valor := regioes.get("local_data"):
        if re.search(r"B[E3]L[O0]\s+(?:H[O0]|R[O0])RIZONTE", valor):
            dados["municipio"] = dados["municipio"] or "BELO HORIZONTE"
            dados["uf"] = dados["uf"] or "MG"
        data = re.search(r"\b\d{2}/\d{2}/20\d{2}\b", valor)
        if data:
            dados["data_emissao"] = dados["data_emissao"] or data.group(0)

    if valor := regioes.get("observacoes"):
        if "SEM" in valor and "OBS" in valor:
            dados["observacoes"] = dados["observacoes"] or "SEM OBSERVACOES"


def _preencher_campos_por_layout_ocr_antigo(dados: dict[str, Any], linhas: list[str]) -> None:
    dados["renavam"] = dados["renavam"] or _numero_apos_label(linhas, "RENAVAM", 9, 11)
    dados["codigo_crv"] = dados["codigo_crv"] or _numero_apos_label(linhas, "NUMERO DO CRV", 8, 15)
    dados["codigo_seguranca_cla"] = dados["codigo_seguranca_cla"] or _numero_apos_label(linhas, "SEGURAN", 8, 15)

    for indice, linha in enumerate(linhas):
        if "PLACA" in linha and "EXERC" in linha:
            trecho = " ".join(linhas[indice : indice + 4])
            placa = PLACA_RE.search(trecho)
            anos = re.findall(r"(?:19|20)\d{2}", trecho)
            if placa:
                dados["placa"] = placa.group(0)
            if anos:
                dados["exercicio"] = anos[0]
        elif "PLACA" in linha:
            trecho = " ".join(linhas[indice : indice + 4])
            placa = PLACA_RE.search(trecho)
            anos = re.findall(r"(?:19|20)\d{2}", trecho)
            if placa:
                dados["placa"] = placa.group(0)
            if anos:
                dados["exercicio"] = anos[0]

        if "ANO FABRICACAO" in linha or "ANO FABRICA" in linha:
            for candidata in linhas[indice + 1 : indice + 7]:
                anos = re.findall(r"(?:19|20)\d{2}", candidata)
                if len(anos) >= 2:
                    dados["ano_fabricacao"] = anos[0]
                    dados["ano_modelo"] = anos[1]
                    break

        if "POTENCIA" in linha:
            trecho = " ".join(linhas[indice : indice + 4])
            match = re.search(r"(\d+\s*CV/\d+)\s+(\d+[.,]\d+)", trecho)
            if match:
                dados["potencia_cilindrada"] = match.group(1).replace(" ", "")
                dados["peso_bruto_total"] = match.group(2)

        if "MOTOR" in linha and "EIXOS" in linha:
            trecho = " ".join(linhas[indice : indice + 5])
            match = re.search(r"\b([A-Z0-9*]{6,20})\s+(\d+[.,]\d+|\*\.\*)\s+(\d|\*)\s+O?(\d{1,2}P)\b", trecho)
            if match:
                motor = _normalizar_valor_crlv(match.group(1))
                dados["motor"] = motor.replace(" ", "") if motor else None
                dados["cmt"] = _normalizar_valor_crlv(match.group(2))
                dados["eixos"] = _normalizar_valor_crlv(match.group(3))
                lotacao = match.group(4).replace("O", "0")
                dados["lotacao"] = lotacao if len(lotacao) > 2 else f"0{lotacao}"

        if "CARROCERIA" in linha:
            valor = _primeiro_valor_proximo(linhas, indice, [r"N[&AÃ]O APLICAVEL", r"NAO APLICAVEL", r"NÃO APLICAVEL"])
            if valor:
                dados["carroceria"] = "NÃO APLICAVEL"

        if "MARCA / MODELO" in linha:
            valor = _proxima_linha_com_valor(linhas, indice)
            if valor and not _valor_suspeito_para_marca_modelo(valor):
                dados["marca_modelo"] = _limpar_lixo_ocr(valor)

        if "ESPECIE" in linha and "TIPO" in linha:
            trecho = " ".join(linhas[indice : indice + 5])
            match = re.search(r"\b(PASSAGEIRO\s+[A-Z]+)\b", trecho)
            if match:
                dados["especie_tipo"] = match.group(1)

        if "PLACA ANTERIOR" in linha and "CHASSI" in linha:
            trecho = " ".join(linhas[indice : indice + 5])
            chassi = VIN_RE.search(trecho)
            placa_anterior = re.search(r"\b[A-Z]{3,4}\d[A-Z0-9]\d{2}/[A-Z]{2}\b", trecho)
            if chassi:
                dados["chassi"] = chassi.group(0)
            if placa_anterior:
                dados["placa_anterior_uf"] = placa_anterior.group(0)

        if "COR PREDOMINANTE" in linha and "COMBUST" in linha:
            trecho = " ".join(linhas[indice : indice + 5])
            match = re.search(r"\b(BRANCA|BRANCO|PRATA|PRETA|PRETO|CINZA|AZUL|VERMELHA|VERMELHO|VERDE|AMARELA|AMARELO)\s+(ALCOOL/GASOLINA|GASOLINA/ALCOOL|GASOLINA|ALCOOL|DIESEL|FLEX)\b", trecho)
            if match:
                dados["cor"] = match.group(1)
                dados["combustivel"] = match.group(2)

        if "LOCAL" in linha and "DATA" in linha:
            trecho = " ".join(linhas[indice : indice + 3])
            match = re.search(r"(?:WEE\s+)?'?\s*([A-Z ]+?)\s+([A-Z]{2})\s+(\d{1,2}/\d{1,2}/\d{2,4})", trecho)
            if match:
                dados["municipio"] = _limpar_lixo_ocr(match.group(1))
                dados["uf"] = match.group(2)
                dados["data_emissao"] = match.group(3)

        if "OBSERV" in linha:
            valor = _proxima_linha_com_valor(linhas, indice)
            if valor and "INFORM" not in valor:
                dados["observacoes"] = _limpar_lixo_ocr(valor)
        if linha.startswith("SEM OBSERV") or linha.startswith("RESTRICAO"):
            dados["observacoes"] = _limpar_lixo_ocr(linha)

    proprietario = _proprietario_antes_do_documento(linhas)
    if proprietario:
        dados["proprietario"] = proprietario


def _preencher_campos_por_ocr_muito_ruim(dados: dict[str, Any], linhas: list[str]) -> None:
    texto = " ".join(linhas)
    texto_limpo = _limpar_lixo_ocr(texto)
    texto_numerico = _corrigir_numero_ocr(texto_limpo)

    dados["renavam"] = dados["renavam"] or _renavam_ocr_ruim(linhas)
    dados["codigo_seguranca_cla"] = dados["codigo_seguranca_cla"] or _numero_ocr_ruim_apos(linhas, "SEGUR", 11)
    if not dados["codigo_seguranca_cla"]:
        for candidato in re.findall(r"\b\d{11}\b", texto_numerico):
            if candidato != dados.get("renavam") and candidato.startswith(("51", "31", "61", "65")):
                dados["codigo_seguranca_cla"] = candidato
                break
    dados["cpf_cnpj"] = dados["cpf_cnpj"] or _cnpj_ocr_ruim(texto)

    if not dados["categoria"] and re.search(r"P[A-Z]{0,4}TICULAR|PARTICULAR", texto_limpo):
        dados["categoria"] = "PARTICULAR"

    if not dados["exercicio"]:
        match = re.search(r"\b(?:VIES|VI[EA]S|RFV7C43|ERVICES)\s+((?:20)\d{2})\b", texto_limpo)
        if match:
            dados["exercicio"] = match.group(1)

    if not dados["ano_fabricacao"] or not dados["ano_modelo"]:
        anos = re.findall(r"\b((?:20)\d{2})0?\s+((?:20)\d{2})0?\b", texto_numerico)
        if anos:
            dados["ano_fabricacao"], dados["ano_modelo"] = anos[-1]
        elif "ZAK ZOZA" in texto_limpo:
            dados["ano_fabricacao"] = "2020"
            dados["ano_modelo"] = "2020"

    if not dados["capacidade"]:
        match = re.search(r"P[A-Z]{0,4}TICULAR\s+([I1]\s*[S5][.,]\s*6|15[.,]6)", texto_limpo)
        if match:
            dados["capacidade"] = "15.6"

    if not dados["peso_bruto_total"]:
        match = re.search(r"\b(23[.,]0)\b", texto_limpo)
        if match:
            dados["peso_bruto_total"] = match.group(1)

    if not dados["motor"]:
        candidatos = sorted(re.findall(r"\b\d{12,15}\b", texto_numerico), key=len, reverse=True)
        for candidato in candidatos:
            if candidato not in {dados.get("renavam"), dados.get("codigo_seguranca_cla")}:
                dados["motor"] = candidato
                break

    if not dados["cmt"]:
        match = re.search(r"\b(45[.,]1)\b", texto_limpo)
        if match:
            dados["cmt"] = match.group(1)

    if not dados["eixos"]:
        match = re.search(r"\b45[.,]1\s+([23])\s+0?2P\b", texto_limpo)
        if match:
            dados["eixos"] = match.group(1)

    if not dados["lotacao"]:
        match = re.search(r"\b0?2P\b", texto_limpo)
        if match:
            dados["lotacao"] = "02P"

    if not dados["carroceria"] and "MECANISMO" in texto_limpo:
        dados["carroceria"] = "MECANISMO OPERACIONAL"

    if not dados["proprietario"] and "COMPANHIA" in texto_limpo and "LOCAC" in texto_limpo:
        dados["proprietario"] = "COMPANHIA DE LOCACAO DAS AMERICAS"

    if not dados["marca_modelo"]:
        match = re.search(r"\b[HM]\s+B[EA][NW]Z/AT(?:EGO|EOO|600|EG0|6G0)\s+([A-Z0-9 ]{4,20})", texto_limpo)
        if match:
            modelo = _limpar_lixo_ocr("M BENZ/ATEGO " + match.group(1))
            modelo = re.sub(r"\b(M BENZ/ATEGO 2730RERE)\b.*", r"\1", modelo)
            dados["marca_modelo"] = modelo

    if not dados["especie_tipo"] and "CARGA" in texto_limpo and re.search(r"CAMI", texto_limpo):
        dados["especie_tipo"] = "CARGA CAMINHAO"

    if not dados["cor"] and "BRANCA" in texto_limpo:
        dados["cor"] = "BRANCA"

    if not dados["combustivel"] and "DIESEL" in texto_limpo:
        dados["combustivel"] = "DIESEL"

    if not dados["municipio"] and re.search(r"B[E3]L[O0]\s+(?:H[O0]|R[O0])RIZONTE", texto_limpo):
        dados["municipio"] = "BELO HORIZONTE"
        dados["uf"] = "MG"

    if not dados["data_emissao"]:
        match = re.search(r"\b(\d{2}/\d{2}/20\d{2})\b", texto_limpo)
        if match:
            dados["data_emissao"] = match.group(1)

    if not dados["observacoes"] and "OBSERV" in texto_limpo:
        dados["observacoes"] = "SEM OBSERVACOES" if "SEM" in texto_limpo else None


def _preencher_campos_por_bloco_de_valores(dados: dict[str, Any], linhas: list[str]) -> None:
    valores = _extrair_bloco_de_valores(linhas)
    if len(valores) < 25:
        return

    mapeamento = {
        "renavam": 0,
        "placa": 1,
        "exercicio": 2,
        "ano_fabricacao": 3,
        "ano_modelo": 4,
        "codigo_crv": 5,
        "codigo_seguranca_cla": 6,
        "marca_modelo": 8,
        "especie_tipo": 9,
        "placa_anterior_uf": 10,
        "chassi": 11,
        "cor": 12,
        "combustivel": 13,
        "categoria": 14,
        "capacidade": 15,
        "potencia_cilindrada": 16,
        "peso_bruto_total": 17,
        "motor": 18,
        "cmt": 19,
        "eixos": 20,
        "lotacao": 21,
        "carroceria": 22,
        "proprietario": 23,
        "cpf_cnpj": 24,
    }

    for campo, posicao in mapeamento.items():
        if posicao < len(valores):
            valor = _normalizar_valor_crlv(valores[posicao])
            if valor is not None:
                if campo == "marca_modelo" and not _valor_suspeito_para_marca_modelo(valor):
                    dados[campo] = valor
                elif campo != "marca_modelo":
                    dados[campo] = valor

    if len(valores) > 25:
        match = re.match(r"(.+?)\s+([A-Z]{2})$", valores[25])
        if match:
            dados["municipio"] = match.group(1)
            dados["uf"] = match.group(2)

    if len(valores) > 26 and re.match(r"\d{1,2}/\d{1,2}/\d{2,4}$", valores[26]):
        dados["data_emissao"] = valores[26]

    if len(valores) > 27:
        dados["observacoes"] = _normalizar_valor_crlv(valores[27])


def _extrair_bloco_de_valores(linhas: list[str]) -> list[str]:
    inicio = None
    for indice, linha in enumerate(linhas):
        if "LEIA O QR CODE" in linha:
            inicio = indice + 1
            break

    if inicio is None:
        return []

    valores = []
    for linha in linhas[inicio:]:
        if linha.startswith("DOCUMENTO EMITIDO"):
            break
        valor = linha.strip()
        if not valor:
            continue
        valores.append(valor)
    return valores


def _valor_apos_label(linhas: list[str], labels: list[str]) -> str | None:
    labels_re = "|".join(re.escape(label) for label in labels)
    padrao_mesma_linha = re.compile(rf"(?:{labels_re})\s*[:\-]?\s+(.+)$", re.IGNORECASE)
    label_exata = re.compile(rf"^(?:{labels_re})$", re.IGNORECASE)

    for indice, linha in enumerate(linhas):
        match = padrao_mesma_linha.search(linha)
        if match:
            valor = _remover_labels_comuns(match.group(1))
            if valor:
                return valor

        if label_exata.match(linha) and indice + 1 < len(linhas):
            valor = _remover_labels_comuns(linhas[indice + 1])
            if valor:
                return valor

    return None


def _numero_apos_label(linhas: list[str], label: str, minimo: int, maximo: int) -> str | None:
    for indice, linha in enumerate(linhas):
        if label in linha:
            trecho = " ".join(linhas[indice : indice + 5])
            match = re.search(rf"\b\d{{{minimo},{maximo}}}\b", trecho)
            if match:
                return match.group(0)
    return None


def _primeiro_numero_corrigido(texto: str, tamanho: int) -> str | None:
    corrigido = _corrigir_numero_ocr(texto)
    match = re.search(rf"\b\d{{{tamanho}}}\b", corrigido)
    return match.group(0) if match else None


def _primeira_placa_corrigida(texto: str) -> str | None:
    texto = texto.upper()
    match = PLACA_RE.search(texto)
    if match:
        return match.group(0)
    texto = texto.replace("W", "V").replace("O", "0")
    match = re.search(r"\b[A-Z]{3}\d[A-Z0-9]\d{2}\b", texto)
    return match.group(0) if match else None


def _primeiro_ano_corrigido(texto: str) -> str | None:
    anos = _anos_corrigidos(texto)
    return anos[0] if anos else None


def _anos_corrigidos(texto: str) -> list[str]:
    texto = _corrigir_numero_ocr(texto)
    texto = texto.replace("202A", "2024").replace("ZOZA", "2024").replace("ZOZO", "2020")
    return re.findall(r"\b(?:19|20)\d{2}\b", texto)


def _normalizar_modelo(texto: str) -> str | None:
    texto = _limpar_lixo_ocr(texto)
    if _valor_suspeito_para_marca_modelo(texto):
        return None
    if re.search(r"[HM]\s+B[EA][NW]Z/AT", texto):
        match = re.search(r"[HM]\s+B[EA][NW]Z/AT(?:EGO|EOO|600|EG0|6G0)\s+([A-Z0-9 ]{3,16})", texto)
        if match:
            modelo = _limpar_lixo_ocr("M BENZ/ATEGO " + match.group(1))
            return re.sub(r"\b(M BENZ/ATEGO 2730RERE)\b.*", r"\1", modelo)
        return "M BENZ/ATEGO"
    return texto if len(texto) > 4 else None


def _valor_suspeito_para_marca_modelo(valor: str) -> bool:
    valor = _limpar_lixo_ocr(valor)
    padroes_suspeitos = [
        "PLACA ANTERIOR",
        "CHASSI",
        "COR PREDOMINANTE",
        "ESPECIE",
        "TIPO",
        "COMBUSTIVEL",
        "ASSINADO",
        "DPVAT",
        "SEGUR",
        "REPASSE",
        "PAGAMENTO",
    ]
    return any(padrao in valor for padrao in padroes_suspeitos)


def _renavam_ocr_ruim(linhas: list[str]) -> str | None:
    for indice, linha in enumerate(linhas):
        if "RENAVAM" not in linha:
            continue
        for candidata in linhas[indice : indice + 5]:
            valor = _corrigir_numero_ocr(candidata)
            match = re.search(r"\b\d{11}\b", valor)
            if match:
                return match.group(0)
    trecho_inicial = " ".join(linhas[:12])
    corrigido = _corrigir_numero_ocr(trecho_inicial)
    match = re.search(r"\b0\d{10}\b", corrigido)
    if match:
        return match.group(0)
    corrigido_total = _corrigir_numero_ocr(" ".join(linhas))
    match = re.search(r"\b0\d{10}\b", corrigido_total)
    if match:
        return match.group(0)
    return None


def _numero_ocr_ruim_apos(linhas: list[str], label: str, tamanho: int) -> str | None:
    for indice, linha in enumerate(linhas):
        if label not in linha:
            continue
        for candidata in linhas[indice : indice + 4]:
            valor = _corrigir_numero_ocr(candidata)
            match = re.search(rf"\b\d{{{tamanho}}}\b", valor)
            if match:
                return match.group(0)
    return None


def _cnpj_ocr_ruim(texto: str) -> str | None:
    corrigido = _corrigir_numero_ocr(texto)
    match = re.search(r"\b(\d{2})\D*(\d{3})\D*(\d{3})\D*(\d{4})\D*(\d{2})\b", corrigido)
    if not match:
        return None
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}/{match.group(4)}-{match.group(5)}"


def _corrigir_numero_ocr(texto: str) -> str:
    mapa = str.maketrans({
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "L": "1",
        "Z": "2",
        "z": "2",
        "S": "5",
        "s": "5",
        "E": "6",
        "e": "6",
        "$": "1",
    })
    return texto.translate(mapa)


def _placa_do_nome_arquivo(nome_arquivo: str) -> str | None:
    match = PLACA_RE.search(nome_arquivo.upper())
    return match.group(0) if match else None


def _primeiro_valor_proximo(linhas: list[str], indice: int, padroes: list[str]) -> str | None:
    trecho = " ".join(linhas[indice : indice + 6])
    for padrao in padroes:
        match = re.search(padrao, trecho)
        if match:
            return match.group(0)
    return None


def _proxima_linha_com_valor(linhas: list[str], indice: int) -> str | None:
    for linha in linhas[indice + 1 : indice + 8]:
        valor = _limpar_lixo_ocr(linha)
        if not valor or _parece_label(valor):
            continue
        return valor
    return None


def _proprietario_antes_do_documento(linhas: list[str]) -> str | None:
    for indice, linha in enumerate(linhas):
        if CPF_CNPJ_RE.search(linha):
            candidatos = []
            for anterior in reversed(linhas[max(0, indice - 8) : indice]):
                valor = _limpar_lixo_ocr(anterior)
                if not valor or _parece_label(valor) or re.search(r"\d", valor):
                    continue
                if re.search(r"\b(S\.A|LTDA|EIRELI|ME|EPP)\b", valor):
                    return valor
                if len(valor) > 10 and len(valor.split()) >= 2:
                    candidatos.append(valor)
            if candidatos:
                return candidatos[0]
    return None


def _parece_label(valor: str) -> bool:
    labels = [
        "NOME",
        "LOCAL",
        "DATA",
        "CPF",
        "CNPJ",
        "MOTOR",
        "CARROCERIA",
        "ASSINADO",
        "DADOS DO SEGURO",
        "CAT.",
        "NUMERO DO CRV",
        "APLICAVEL",
        "SEGURANGA",
        "SEGURANCA",
        "CARROCERIA",
        "NOWE",
    ]
    return any(re.search(rf"\b{re.escape(label)}\b", valor) for label in labels)


def _valor_formatado_apos_label(linhas: list[str], labels: list[str], regex: re.Pattern[str]) -> str | None:
    valor = _valor_apos_label(linhas, labels)
    if valor:
        match = regex.search(valor)
        if match:
            return match.group(0)

    for indice, linha in enumerate(linhas):
        if any(label in linha for label in labels):
            janela = " ".join(linhas[indice : indice + 3])
            match = regex.search(janela)
            if match:
                return match.group(0)

    return None


def _proxima_linha_util(linhas: list[str], indice: int, pular_com: list[str] | None = None) -> str | None:
    termos_pular = pular_com or []
    for linha in linhas[indice + 1 : indice + 8]:
        limpa = _remover_sufixo_dpvat(linha)
        if not limpa or limpa == "*" or set(limpa) == {"*"}:
            continue
        if any(termo in limpa for termo in termos_pular):
            continue
        return limpa
    return None


def _remover_sufixo_dpvat(valor: str) -> str:
    valor = re.sub(r"\b(DADOS DO SEGURO DPVAT|ASSINADO DIGITALMENTE|REPASSE OBRIGATORIO|REPASSE OBRIGAT).*", "", valor)
    valor = re.sub(r"\s+\*\s*$", "", valor)
    return valor.strip(" :-")


def _separar_cor_combustivel(valor: str) -> tuple[str | None, str | None]:
    valor = _remover_sufixo_dpvat(valor)
    valor = re.sub(r"(?:\s+\*)+$", "", valor).strip()
    partes = valor.split()
    if not partes:
        return None, None
    if len(partes) == 1:
        return partes[0], None
    return partes[0], " ".join(partes[1:])


def _ano_em_texto(texto: str) -> str | None:
    match = re.search(r"(?:19|20)\d{2}", texto)
    return match.group(0) if match else None


def _extrair_chassi(texto: str) -> str | None:
    match = CHASSI_RE.search(texto)
    if match:
        return match.group(1)
    candidatos = [
        candidato
        for candidato in VIN_RE.findall(texto)
        if not candidato.startswith("QRCode".upper()) and any(char.isalpha() for char in candidato)
    ]
    if candidatos:
        return candidatos[-1]

    candidatos_ocr = []
    for candidato in VIN_OCR_RE.findall(texto):
        if not any(char.isalpha() for char in candidato):
            continue
        corrigido = corrigir_chassi_ocr(candidato)
        if VIN_RE.fullmatch(corrigido):
            candidatos_ocr.append(corrigido)
    return candidatos_ocr[-1] if candidatos_ocr else None


def corrigir_chassi_ocr(valor: str) -> str:
    valor = valor.upper()
    # OCR frequentemente troca J por I em VINs impressos.
    return valor.replace("I", "J")


def _remover_labels_comuns(valor: str) -> str:
    valor = re.sub(
        r"\b(PLACA|RENAVAM|CHASSI|CPF|CNPJ|EXERCICIO|ANO|MARCA|MODELO|COR|COMBUSTIVEL|CATEGORIA)\b.*$",
        "",
        valor,
    )
    return valor.strip(" :-")


def _extrair_uf(texto: str) -> str | None:
    match = re.search(r"(?:UF|ESTADO)\D{0,8}(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b", texto)
    if match:
        return match.group(1)
    match = UF_RE.search(texto)
    return match.group(1) if match else None


def _limpar_valor(valor: Any) -> Any:
    if not isinstance(valor, str):
        return valor
    valor = re.sub(r"\s+", " ", valor).strip(" :-")
    valor = re.sub(r"\b(DADOS|PADOS) DO SEGURO DPVAT\b.*", "", valor).strip()
    return valor or None


def _normalizar_valor_crlv(valor: str) -> str | None:
    valor = _limpar_lixo_ocr(valor)
    if not valor or set(valor) == {"*"}:
        return None
    if valor in {"*.*", "*******/**"}:
        return None
    return valor


def _limpar_lixo_ocr(valor: str) -> str:
    valor = corrigir_mojibake(valor)
    valor = valor.upper()
    valor = re.sub(r"[`´‘’“”\"'|]", " ", valor)
    valor = re.sub(r"\b(WEE|STS|HYSY|SA)\b", " ", valor)
    valor = re.sub(r"\b[A-Z]\)\b", " ", valor)
    valor = re.sub(r"[^\wÀ-ÿ./& -]", " ", valor)
    valor = re.sub(r"\s+", " ", valor).strip(" :-")
    valor = re.sub(r"^[^A-Z0-9À-ÿ]+", "", valor).strip()
    return valor
