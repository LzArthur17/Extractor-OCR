# Agente OCR para documentos

Pipeline local para processar varios PDFs/imagens de CRLV, extrair texto e retornar informacoes estruturadas em JSON e Excel.

## Fluxo

1. Coloque os arquivos em `documentos_entrada/`.
2. O sistema tenta extrair texto direto do PDF.
3. Se nao houver texto, converte paginas em imagem e usa OCR.
4. Para CRLV, os campos sao extraidos por regras rapidas.
5. Se o score ficar abaixo de 85, roda uma segunda tentativa de OCR refinado com limite de tempo.
6. Opcionalmente, o Ollama pode ser usado como fallback quando as regras nao encontrarem dados suficientes.
7. A resposta e validada e salva em `saida/resultados.json` e `saida/resultados.xlsx`.

## Instalar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Para OCR em imagem, instale tambem o Tesseract no Windows e deixe o executavel no PATH:

```powershell
winget install UB-Mannheim.TesseractOCR
```

Baixe um modelo no Ollama:

```powershell
ollama pull llama3.1
```

## Usar

```powershell
python -m src.main
```

O processamento usa cache em `saida/textos_ocr/`. Se rodar de novo os mesmos documentos, ele reaproveita o texto extraido e evita OCR novamente.

Para usar mais ou menos processamento paralelo:

```powershell
python -m src.main --workers 4
```

Para reprocessar OCR do zero:

```powershell
python -m src.main --force-ocr
```

Por padrao, documentos com `score_confianca` menor que 85 passam por retry progressivo por ate 12 segundos. O sistema tenta primeiro OCR apenas nas regioes dos campos faltantes; se ainda ficar abaixo do limite, usa o OCR refinado completo com o tempo restante. Para ajustar:

```powershell
python -m src.main --retry-min-score 85 --ocr-retry-timeout 12
```

Para desativar a segunda tentativa e priorizar velocidade maxima:

```powershell
python -m src.main --disable-ocr-retry
```

Para usar Ollama apenas como fallback quando as regras do CRLV falharem:

```powershell
python -m src.main --use-ollama-fallback --model qwen2.5
```

Com campos personalizados:

```powershell
python -m src.main --fields placa renavam chassi proprietario cpf_cnpj exercicio
```

## Usar como API para outro sistema

Inicie a API:

```powershell
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

Endpoint principal:

```http
POST /api/crlv/extrair
```

Campo multipart:

```text
arquivo=<PDF ou imagem>
```

Exemplo de retorno:

```json
{
  "arquivo": "CRLV.pdf",
  "status": "ok",
  "score_confianca": 93,
  "metodo": "regras_crlv+ocr_refinado",
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

Documentacao interativa:

```text
http://localhost:8000/docs
```

## Testes

```powershell
pytest
```

## Configuracao

Variaveis principais:

```text
RETRY_MIN_SCORE=85
OCR_RETRY_TIMEOUT_SECONDS=12
ENABLE_OCR_RETRY=true
REVIEW_MIN_SCORE=90
MAX_PAGES=1
```

## Pastas

- `documentos_entrada/`: coloque PDFs, PNGs, JPGs, JPEGs, TIFFs e BMPs aqui.
- `saida/textos_ocr/`: textos extraidos por arquivo.
- `saida/resultados.json`: resultado completo.
- `saida/resultados.xlsx`: planilha para conferencia.
