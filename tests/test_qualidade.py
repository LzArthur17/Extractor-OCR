from src.qualidade import avaliar_qualidade, documento_valido


def test_documento_valido_verifica_cpf_e_cnpj():
    assert documento_valido("529.982.247-25")
    assert documento_valido("04.437.534/0014-55")
    assert not documento_valido("10.225.988/0002-46")


def test_score_baixa_quando_campos_obrigatorios_faltam():
    qualidade = avaliar_qualidade({
        "placa": "ABC1D23",
        "renavam": "12345678900",
    })

    assert qualidade["score_confianca"] < 70


def test_score_penaliza_cnpj_invalido():
    campos = {
        "placa": "ABC1D23",
        "renavam": "12345678900",
        "chassi": "9BWZZZ377VT004251",
        "exercicio": "2024",
        "ano_fabricacao": "2023",
        "ano_modelo": "2024",
        "marca_modelo": "FIAT/ARGO",
        "proprietario": "CLIENTE TESTE",
        "cpf_cnpj": "10.225.988/0002-46",
        "municipio": "SAO PAULO",
        "uf": "SP",
    }

    qualidade = avaliar_qualidade(campos)

    assert qualidade["score_confianca"] < 85

