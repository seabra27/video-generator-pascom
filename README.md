# Pipeline de Vídeo do Evangelho — Pascom

Projeto interno da Pascom (Basílica Nossa Senhora de Lourdes, Vila Isabel, RJ) para
transformar o áudio do Evangelho dominical em um vídeo com imagens animadas
sincronizadas.

> Este README está em construção. A versão final (Fase 7) vai documentar como
> abrir o app pela interface Streamlit, sem exigir uso de terminal por quem
> não é da equipe técnica.

## Status do projeto

- [x] Fase 1 — Setup do projeto
- [ ] Fase 2 — Transcrição local (faster-whisper)
- [ ] Fase 3 — Segmentação + prompt de cena (Anthropic API)
- [ ] Fase 4 — Geração de imagem (fal.ai)
- [ ] Fase 5 — Montagem de vídeo (FFmpeg/MoviePy)
- [ ] Fase 6 — App interativo (Streamlit)
- [ ] Fase 7 — README final

## Estrutura

```
core/               → lógica pura (sem dependência de interface)
├── transcription/      → Whisper local, sem chave de API
├── segmentation/        → LLM (Anthropic) → blocos temáticos + prompt de imagem
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

### Anthropic API (Fase 3 — segmentação e prompt de cena)
1. Acesse https://console.anthropic.com e crie uma conta.
2. Vá em **Billing** e adicione um cartão (uso pay-as-you-go).
3. Vá em **API Keys** → **Create Key**.
4. Cole o valor gerado em `ANTHROPIC_API_KEY` no arquivo `.env`.

### fal.ai (Fase 4 — geração de imagem)
1. Acesse https://fal.ai e crie uma conta.
2. No dashboard, vá na seção de chaves de API e gere uma nova chave.
3. Configure o billing pay-as-you-go.
4. Cole o valor gerado em `FAL_KEY` no arquivo `.env`.

Essas instruções serão repetidas dentro do app quando a fase correspondente
for implementada.
