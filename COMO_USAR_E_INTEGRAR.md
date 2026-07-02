# Como usar e integrar o Extractor OCR

Este projeto extrai dados de CRLV a partir de PDF ou imagem e devolve os campos prontos para preencher uma tela web.

## 1. Instalar dependencias

No terminal, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Para documentos escaneados/imagem, instale o Tesseract:

```powershell
winget install UB-Mannheim.TesseractOCR
```

## 2. Rodar como API

```powershell
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

Abra a documentacao:

```text
http://localhost:8000/docs
```

Teste de saude:

```text
http://localhost:8000/health
```

## 3. Endpoint principal

```http
POST /api/crlv/extrair
```

Envie o arquivo no campo multipart chamado:

```text
arquivo
```

Exemplo de retorno:

```json
{
  "arquivo": "CRLV.pdf",
  "status": "ok",
  "score_confianca": 97,
  "metodo": "regras_crlv",
  "campos": {
    "placa": "ABC1D23",
    "renavam": "12345678900",
    "chassi": "9BW...",
    "codigo_crv": "123456789012",
    "marca_modelo": "FIAT/ARGO",
    "cor": "BRANCA",
    "combustivel": "FLEX",
    "categoria": "PARTICULAR",
    "ano_fabricacao": "2022",
    "ano_modelo": "2023",
    "proprietario": "NOME DO PROPRIETARIO",
    "cpf_cnpj": "00.000.000/0000-00",
    "uf": "SP"
  }
}
```

## 4. Integrar em uma tela web

Exemplo em JavaScript:

```javascript
async function extrairCRLV(file) {
  const formData = new FormData();
  formData.append("arquivo", file);

  const response = await fetch("http://localhost:8000/api/crlv/extrair", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Erro ao extrair CRLV");
  }

  return response.json();
}
```

Preenchendo os campos:

```javascript
const resultado = await extrairCRLV(arquivoSelecionado);
const campos = resultado.campos;

document.querySelector("#cliente").value = campos.proprietario ?? "";
document.querySelector("#documento_cliente").value = campos.cpf_cnpj ?? "";
document.querySelector("#placa").value = campos.placa ?? "";
document.querySelector("#chassi").value = campos.chassi ?? "";
document.querySelector("#renavam").value = campos.renavam ?? "";
document.querySelector("#marca_modelo").value = campos.marca_modelo ?? "";
document.querySelector("#cor").value = campos.cor ?? "";
document.querySelector("#combustivel").value = campos.combustivel ?? "";
document.querySelector("#categoria").value = campos.categoria ?? "";
document.querySelector("#ano_fabricacao").value = campos.ano_fabricacao ?? "";
document.querySelector("#ano_modelo").value = campos.ano_modelo ?? "";
document.querySelector("#crv").value = campos.codigo_crv ?? "";
document.querySelector("#uf_origem").value = campos.uf ?? "";
document.querySelector("#doc_proprietario").value = campos.cpf_cnpj ?? "";
```

## 5. Score de confianca

O campo `score_confianca` vai de 0 a 100.

Sugestao simples:

- `90` a `100`: preencher automaticamente.
- `70` a `89`: preencher, mas destacar para conferencia.
- abaixo de `70`: pedir conferencia manual antes de salvar.

## 6. Configuracao por ambiente

Voce pode copiar `.env.example` como referencia para configurar:

```text
CORS_ORIGINS=*
OLLAMA_MODEL=llama3.1
OLLAMA_URL=http://localhost:11434
REVIEW_MIN_SCORE=90
MAX_PAGES=1
```

Por padrao, a API funciona sem Ollama. O Ollama e usado apenas se o endpoint receber `usar_ollama=true`.

## 7. Rodar testes

```powershell
pytest
```

Os testes conferem:

- contrato basico da API;
- rejeicao de arquivo invalido;
- validacao de CPF/CNPJ e score.

## 8. Rodar em lote

Coloque os PDFs em `documentos_entrada/` e execute:

```powershell
python -m src.main
```

Os resultados ficam em:

```text
saida/resultados.json
saida/resultados.xlsx
```
