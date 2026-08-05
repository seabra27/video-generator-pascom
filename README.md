# Pipeline de Vídeo do Evangelho — Pascom

Projeto interno da Pascom (Basílica Nossa Senhora de Lourdes, Vila Isabel, RJ) para
transformar o áudio do Evangelho dominical em um vídeo com imagens animadas
sincronizadas.

> Este README está em construção. A versão final (Fase 7) vai documentar como
> abrir o app pela interface Streamlit, sem exigir uso de terminal por quem
> não é da equipe técnica.

## Status do projeto

- [x] Fase 1 — Setup do projeto
- [x] Fase 2 — Transcrição local (faster-whisper)
- [x] Fase 3 — Segmentação + prompt de cena (Google Gemini, tier gratuito)
- [ ] Fase 4 — Geração de imagem (fal.ai)
- [ ] Fase 5 — Montagem de vídeo (FFmpeg/MoviePy)
- [ ] Fase 6 — App interativo (Streamlit)
- [ ] Fase 7 — README final

## Estrutura

```
core/               → lógica pura (sem dependência de interface)
├── transcription/      → Whisper local, sem chave de API
├── segmentation/        → LLM (Google Gemini) → blocos temáticos + prompt de imagem
├── image_generation/    → fal.ai/Flux → imagens por bloco
└── assembly/             → FFmpeg/MoviePy → Ken Burns/parallax + cross-fade

app/                → interface Streamlit, orquestra core/
output/             → vídeos finais (.mp4)
input_examples/     → áudios de exemplo para teste isolado de cada fase
```

> Nota: os módulos de `core/` usam nomes de pasta válidos como pacote Python
> (`transcription`, `segmentation`, ...) em vez de `1_transcription` etc.,
> porque nomes de pacote não podem começar com dígito em Python. A ordem das
> fases é a mesma descrita no planejamento original.

## Setup do ambiente (dev)

Pré-requisito: **Python 3.12** (já instalado neste projeto via winget — o
`faster-whisper`, usado na Fase 2, depende do `ctranslate2`, que ainda não
tem build para o Python 3.14).

```powershell
py -3.12 -m venv venv
./venv/Scripts/pip install -r requirements.txt
```

O arquivo `.env` (copiado de `.env.example`) guarda as chaves de API. Veja a
seção de chaves abaixo antes das Fases 3 e 4.

## Chaves de API

### Google Gemini (Fase 3 — segmentação e prompt de cena)
Usamos o Gemini em vez de um provider pago porque essa etapa (dividir texto
em blocos e escrever prompts de imagem) não exige o modelo mais caro do
mercado, e o tier gratuito do Google não pede cartão de crédito — importante
para um projeto paroquial sem orçamento.
1. Acesse https://aistudio.google.com/apikey e entre com uma conta Google.
2. Clique em **Create API key** (crie um projeto novo se pedir).
3. Copie o valor gerado (começa com `AIza`).
4. Cole esse valor em `GEMINI_API_KEY` no arquivo `.env`.

O modelo usado (`gemini-3.5-flash-lite`) fica dentro do tier gratuito para o
volume de uso deste projeto (poucas chamadas por vídeo, uma vez por semana).
Se a cota gratuita for excedida, o app mostra uma mensagem clara pedindo pra
aguardar alguns minutos.

### fal.ai (Fase 4 — geração de imagem)
1. Acesse https://fal.ai e crie uma conta.
2. No dashboard, vá na seção de chaves de API e gere uma nova chave.
3. Configure o billing pay-as-you-go.
4. Cole o valor gerado em `FAL_KEY` no arquivo `.env`.

Essas instruções serão repetidas dentro do app quando a fase correspondente
for implementada.
