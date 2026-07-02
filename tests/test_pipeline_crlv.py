from pathlib import Path

import src.pipeline_crlv as pipeline


def test_nao_roda_ocr_refinado_quando_score_e_alto(monkeypatch, tmp_path):
    arquivo = tmp_path / "documento.pdf"
    arquivo.write_bytes(b"%PDF fake")

    def fake_texto(*args, **kwargs):
        return "texto inicial"

    def fake_extrair(*args, **kwargs):
        return {
            "placa": "ABC1D23",
            "renavam": "12345678900",
            "chassi": "9BWZZZ377VT004251",
            "exercicio": "2024",
            "ano_fabricacao": "2023",
            "ano_modelo": "2024",
            "marca_modelo": "FIAT/ARGO",
            "proprietario": "CLIENTE TESTE",
            "cpf_cnpj": "529.982.247-25",
            "municipio": "SAO PAULO",
            "uf": "SP",
            "codigo_crv": "123456789012",
            "codigo_seguranca_cla": "12345678901",
            "motor": "123456789012",
            "cor": "BRANCA",
            "combustivel": "FLEX",
            "categoria": "PARTICULAR",
            "especie_tipo": "PASSAGEIRO AUTOMOVEL",
            "data_emissao": "01/01/2024",
            "capacidade": "5",
            "potencia_cilindrada": "100CV/999",
            "peso_bruto_total": "1.5",
            "cmt": "2.0",
            "eixos": "2",
            "lotacao": "05P",
            "carroceria": "NAO APLICAVEL",
        }

    def falha_se_chamar(*args, **kwargs):
        raise AssertionError("OCR refinado nao deveria rodar")

    monkeypatch.setattr(pipeline, "extrair_texto_documento", fake_texto)
    monkeypatch.setattr(pipeline, "extrair_crlv", fake_extrair)
    monkeypatch.setattr(pipeline, "extrair_texto_documento_refinado", falha_se_chamar)

    resultado = pipeline.extrair_crlv_com_retry_ocr(arquivo)

    assert resultado["metodo"] == "regras_crlv"
    assert not resultado["ocr_refinado_usado"]


def test_roda_ocr_refinado_quando_score_e_baixo(monkeypatch, tmp_path):
    arquivo = tmp_path / "documento.pdf"
    arquivo.write_bytes(b"%PDF fake")
    chamadas = {"refinado": 0}

    def fake_texto(*args, **kwargs):
        return "texto inicial sem campos"

    def fake_texto_refinado(*args, **kwargs):
        chamadas["refinado"] += 1
        return "texto refinado com campos"

    def fake_extrair(texto, *args, **kwargs):
        if "refinado" not in texto:
            return {"placa": "ABC1D23", "renavam": "12345678900"}
        return {
            "placa": "ABC1D23",
            "renavam": "12345678900",
            "chassi": "9BWZZZ377VT004251",
            "exercicio": "2024",
            "ano_fabricacao": "2023",
            "ano_modelo": "2024",
            "marca_modelo": "FIAT/ARGO",
            "proprietario": "CLIENTE TESTE",
            "cpf_cnpj": "529.982.247-25",
            "municipio": "SAO PAULO",
            "uf": "SP",
            "codigo_crv": "123456789012",
            "codigo_seguranca_cla": "12345678901",
            "motor": "123456789012",
            "cor": "BRANCA",
            "combustivel": "FLEX",
            "categoria": "PARTICULAR",
            "especie_tipo": "PASSAGEIRO AUTOMOVEL",
            "data_emissao": "01/01/2024",
            "capacidade": "5",
        }

    monkeypatch.setattr(pipeline, "extrair_texto_documento", fake_texto)
    monkeypatch.setattr(pipeline, "extrair_texto_documento_refinado", fake_texto_refinado)
    monkeypatch.setattr(pipeline, "extrair_crlv", fake_extrair)

    resultado = pipeline.extrair_crlv_com_retry_ocr(arquivo)

    assert chamadas["refinado"] == 1
    assert resultado["metodo"] == "regras_crlv+ocr_regioes"
    assert resultado["campos"]["chassi"] == "9BWZZZ377VT004251"


def test_roda_ocr_completo_se_regioes_nao_melhorarem(monkeypatch, tmp_path):
    arquivo = tmp_path / "documento.pdf"
    arquivo.write_bytes(b"%PDF fake")
    chamadas = []

    def fake_texto(*args, **kwargs):
        return "texto inicial sem campos"

    def fake_texto_refinado(*args, **kwargs):
        chamadas.append(kwargs["somente_regioes"])
        if kwargs["somente_regioes"]:
            return "texto regioes sem ganho"
        return "texto completo com campos"

    def fake_extrair(texto, *args, **kwargs):
        if "completo" not in texto:
            return {"placa": "ABC1D23", "renavam": "12345678900"}
        return {
            "placa": "ABC1D23",
            "renavam": "12345678900",
            "chassi": "9BWZZZ377VT004251",
            "exercicio": "2024",
            "ano_fabricacao": "2023",
            "ano_modelo": "2024",
            "marca_modelo": "FIAT/ARGO",
            "proprietario": "CLIENTE TESTE",
            "cpf_cnpj": "529.982.247-25",
            "municipio": "SAO PAULO",
            "uf": "SP",
        }

    monkeypatch.setattr(pipeline, "extrair_texto_documento", fake_texto)
    monkeypatch.setattr(pipeline, "extrair_texto_documento_refinado", fake_texto_refinado)
    monkeypatch.setattr(pipeline, "extrair_crlv", fake_extrair)

    resultado = pipeline.extrair_crlv_com_retry_ocr(arquivo)

    assert chamadas == [True, False]
    assert resultado["metodo"] == "regras_crlv+ocr_refinado"
    assert resultado["campos"]["chassi"] == "9BWZZZ377VT004251"


def test_timeout_no_ocr_refinado_retorna_campos_parciais(monkeypatch, tmp_path):
    arquivo = tmp_path / "documento.pdf"
    arquivo.write_bytes(b"%PDF fake")

    def fake_texto(*args, **kwargs):
        return "texto inicial com poucos campos"

    def fake_texto_refinado(*args, **kwargs):
        raise RuntimeError("Tesseract process timeout")

    def fake_extrair(*args, **kwargs):
        return {"placa": "RFV7C43", "renavam": "12345678900"}

    monkeypatch.setattr(pipeline, "extrair_texto_documento", fake_texto)
    monkeypatch.setattr(pipeline, "extrair_texto_documento_refinado", fake_texto_refinado)
    monkeypatch.setattr(pipeline, "extrair_crlv", fake_extrair)

    resultado = pipeline.extrair_crlv_com_retry_ocr(arquivo)

    assert resultado["metodo"] == "regras_crlv"
    assert resultado["ocr_refinado_usado"]
    assert "Tesseract process timeout" in resultado["aviso"]
    assert resultado["campos"]["placa"] == "RFV7C43"
    assert resultado["campos"]["renavam"] == "12345678900"
