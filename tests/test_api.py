from fastapi.testclient import TestClient

import src.api as api


def test_health():
    client = TestClient(api.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_rejeita_extensao_nao_suportada():
    client = TestClient(api.app)
    response = client.post(
        "/api/crlv/extrair",
        files={"arquivo": ("documento.txt", b"teste", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_retorna_contrato_fixo(monkeypatch):
    def fake_extrair_crlv_com_retry_ocr(*args, **kwargs):
        return {
            "texto": "texto OCR",
            "metodo": "regras_crlv",
            "qualidade": {"score_confianca": 91},
            "campos": {
                "tipo_documento": "CRLV",
                "placa": "ABC1D23",
                "renavam": "12345678900",
                "chassi": "9BWZZZ377VT004251",
                "codigo_crv": "123456789012",
                "exercicio": "2024",
                "ano_fabricacao": "2023",
                "ano_modelo": "2024",
                "marca_modelo": "FIAT/ARGO",
                "proprietario": "CLIENTE TESTE",
                "cpf_cnpj": "529.982.247-25",
                "municipio": "SAO PAULO",
                "uf": "SP",
            },
        }

    monkeypatch.setattr(api, "extrair_crlv_com_retry_ocr", fake_extrair_crlv_com_retry_ocr)

    client = TestClient(api.app)
    response = client.post(
        "/api/crlv/extrair",
        files={"arquivo": ("documento.pdf", b"%PDF fake", "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"arquivo", "status", "score_confianca", "metodo", "campos"}
    assert body["campos"]["placa"] == "ABC1D23"
    assert body["campos"]["proprietario"] == "CLIENTE TESTE"
