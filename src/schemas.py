from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CrlvCampos(BaseModel):
    tipo_documento: str | None = None
    placa: str | None = None
    renavam: str | None = None
    chassi: str | None = None
    codigo_crv: str | None = None
    codigo_seguranca_cla: str | None = None
    exercicio: str | None = None
    ano_fabricacao: str | None = None
    ano_modelo: str | None = None
    marca_modelo: str | None = None
    capacidade: str | None = None
    potencia_cilindrada: str | None = None
    peso_bruto_total: str | None = None
    motor: str | None = None
    cmt: str | None = None
    eixos: str | None = None
    lotacao: str | None = None
    carroceria: str | None = None
    cor: str | None = None
    combustivel: str | None = None
    categoria: str | None = None
    especie_tipo: str | None = None
    placa_anterior_uf: str | None = None
    proprietario: str | None = None
    cpf_cnpj: str | None = None
    municipio: str | None = None
    uf: str | None = None
    data_emissao: str | None = None
    observacoes: str | None = None


class ExtracaoResponse(BaseModel):
    arquivo: str
    status: Literal["ok"]
    score_confianca: int = Field(ge=0, le=100)
    metodo: str
    campos: CrlvCampos


class HealthResponse(BaseModel):
    status: Literal["ok"]
