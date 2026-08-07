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
- [x] Fase 4 — Geração de imagem (Cloudflare Workers AI / Flux, tier gratuito)
- [x] Fase 5 — Montagem de vídeo (FFmpeg/MoviePy)
- [x] Fase 6 — App interativo (Streamlit)
- [ ] Fase 7 — README final

## Estrutura

```
core/               → lógica pura (sem dependência de interface)
├── transcription/      → Whisper local, sem chave de API
├── segmentation/        → LLM (Google Gemini) → blocos temáticos + prompt de imagem
├── image_generation/    → Cloudflare Workers AI (Flux) → imagens por bloco
└── assembly/             → FFmpeg/MoviePy → Ken Burns/parallax + cross-fade

app/main.py         → interface Streamlit (passo a passo), orquestra core/
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

## Como rodar o app

```powershell
./venv/Scripts/streamlit run app/main.py
```

Abre automaticamente no navegador (http://localhost:8501). O app guia o
processo em 4 passos — enviar o áudio, transcrever, dividir em blocos,
gerar/escolher as imagens de cada bloco e montar o vídeo final — e cada
passo só aparece depois que o anterior termina. Erros de chave de API
ausente/inválida ou cota esgotada aparecem na tela, com instruções de como
resolver, sem precisar abrir o terminal.

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

### Cloudflare Workers AI (Fase 4 — geração de imagem)
Trocamos o fal.ai (proposta original) pelo Cloudflare Workers AI porque essa
etapa tem custo real e o projeto não tem orçamento — o tier gratuito do
Cloudflare (10.000 "neurons"/dia, sem cartão) dá ~230 imagens grátis por dia
usando o mesmo modelo Flux (Flux 1 Schnell) previsto originalmente.
1. Acesse https://dash.cloudflare.com/sign-up e crie uma conta.
2. No painel, vá em **AI** → **Workers AI**.
3. Anote o **Account ID** (barra lateral direita do dashboard).
4. Vá em **My Profile** → **API Tokens** → **Create Token**, use o template
   "Workers AI", e copie o token gerado.
5. Cole os dois valores no `.env`: `CLOUDFLARE_API_TOKEN` e
   `CLOUDFLARE_ACCOUNT_ID`.

> Se a geração de imagem falhar com "Credenciais ausentes ou inválidas" mesmo
> com os dois valores preenchidos corretamente, confira se o token não tem
> **filtragem de IP** ativada (Cloudflare → **My Profile** → **API Tokens** →
> editar o token → **Client IP Address Filtering**). Um token restrito a um
> IP recusa pedidos vindos de qualquer outra rede — remova o filtro ou
> adicione o IP atual.

> Nota de qualidade: o Flux 1 Schnell é a variante rápida do Flux (a mesma
> família usada por serviços pagos como o fal.ai), então às vezes gera rostos
> um pouco mais realistas do que o guia de estilo pede, mesmo com a instrução
> "sem fotorrealismo" no prompt. Isso é uma limitação do modelo rápido/grátis,
> não do código — a Fase 6 (app) tem botão de "regenerar cena" para escolher
> a melhor variação entre as geradas.

Essas instruções aparecem automaticamente dentro do app (Fase 6) sempre que
uma chave estiver ausente, inválida ou com a cota esgotada.
