"""
Geração de imagens de fundo para cada bloco, via Cloudflare Workers AI
(modelo Flux 1 Schnell), mantendo o guia de estilo fixo (core/style.py) em
todas as chamadas para não haver quebra de estilo entre blocos.

Função pura: recebe um prompt de imagem (já pronto, gerado na Fase 3) e
devolve os bytes da imagem. Não depende de Streamlit nem de nenhuma outra
camada de interface.

Requer as variáveis de ambiente CLOUDFLARE_API_TOKEN e CLOUDFLARE_ACCOUNT_ID
(ver README — seção "Chaves de API"). Usamos o Cloudflare Workers AI em vez
do fal.ai (proposta original) porque essa etapa de geração de imagem tem
custo real, e o projeto não tem orçamento agora — o tier gratuito do
Cloudflare (10.000 "neurons"/dia, sem cartão de crédito) dá umas 230
imagens grátis por dia, muito acima do necessário para um vídeo semanal, e
já usa o mesmo modelo Flux previsto originalmente.
"""

import base64
import logging
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("pascom.geracao_imagem")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

MODELO_PADRAO = "@cf/black-forest-labs/flux-1-schnell"
LARGURA_PADRAO = 1024
ALTURA_PADRAO = 576  # 16:9, mesma proporção do vídeo final

# Usados para a estimativa de uso mostrada no app antes de gerar as imagens.
NEURONS_POR_IMAGEM = 43
LIMITE_GRATUITO_NEURONS_DIA = 10_000

INSTRUCOES_CHAVE_CLOUDFLARE = (
    "Credenciais do Cloudflare Workers AI ausentes ou inválidas.\n"
    "Como conseguir (gratuito, sem cartão de crédito):\n"
    "1. Acesse https://dash.cloudflare.com/sign-up e crie uma conta.\n"
    "2. No painel, vá em 'AI' -> 'Workers AI'.\n"
    "3. Anote o 'Account ID' (barra lateral direita do dashboard).\n"
    "4. Vá em 'My Profile' -> 'API Tokens' -> 'Create Token', use o template "
    "'Workers AI', e copie o token gerado.\n"
    "5. Cole os dois valores no .env: CLOUDFLARE_API_TOKEN e CLOUDFLARE_ACCOUNT_ID."
)


class ChaveApiAusenteError(Exception):
    """Levantado quando as credenciais do Cloudflare não estão configuradas, são inválidas, ou a cota diária acabou."""


def _url_da_api(account_id: str, modelo: str) -> str:
    return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{modelo}"


def _credenciais() -> tuple[str, str]:
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token or not account_id:
        raise ChaveApiAusenteError(INSTRUCOES_CHAVE_CLOUDFLARE)
    return token, account_id


def generate_image(
    prompt: str,
    width: int = LARGURA_PADRAO,
    height: int = ALTURA_PADRAO,
    seed: int | None = None,
    model: str = MODELO_PADRAO,
) -> bytes:
    """
    Gera uma imagem a partir de um prompt e devolve os bytes (PNG).

    O prompt já deve incluir o guia de estilo (isso é feito na Fase 3, ao
    escrever "prompt_imagem" de cada bloco — ver core/style.py).
    """
    token, account_id = _credenciais()

    payload: dict = {"prompt": prompt, "width": width, "height": height}
    if seed is not None:
        payload["seed"] = seed

    inicio = time.time()
    resposta = requests.post(
        _url_da_api(account_id, model),
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )

    if resposta.status_code == 401:
        raise ChaveApiAusenteError(INSTRUCOES_CHAVE_CLOUDFLARE)
    if resposta.status_code == 429:
        raise ChaveApiAusenteError(
            "Cota gratuita diária do Cloudflare Workers AI esgotada (~230 imagens/dia).\n"
            "Aguarde até a meia-noite UTC para renovar, ou tente novamente mais tarde."
        )
    resposta.raise_for_status()

    corpo = resposta.json()
    if not corpo.get("success"):
        raise RuntimeError(f"Cloudflare Workers AI retornou erro: {corpo.get('errors')}")

    imagem_bytes = base64.b64decode(corpo["result"]["image"])
    logger.info("Imagem gerada em %.1fs (%d bytes).", time.time() - inicio, len(imagem_bytes))
    return imagem_bytes


def generate_images_for_block(
    prompt: str,
    n_imagens: int = 3,
    width: int = LARGURA_PADRAO,
    height: int = ALTURA_PADRAO,
) -> list[bytes]:
    """
    Gera várias imagens (variações) para o mesmo bloco, usando seeds
    diferentes — necessário para o cross-fade/Ken Burns com múltiplas
    imagens por bloco (Fase 5).
    """
    logger.info("Gerando %d imagens para o bloco...", n_imagens)
    imagens = []
    for i in range(n_imagens):
        imagens.append(generate_image(prompt, width=width, height=height, seed=i))
    return imagens


def salvar_imagem(imagem_bytes: bytes, output_path: str) -> None:
    """Salva os bytes da imagem em disco (cria a pasta de destino se preciso)."""
    from pathlib import Path

    destino = Path(output_path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(imagem_bytes)
    logger.info("Imagem salva em '%s'.", destino)


def estimar_uso(n_blocos: int, imagens_por_bloco: int = 3) -> dict:
    """
    Estimativa de uso (não é custo em dinheiro — o Cloudflare Workers AI é
    gratuito dentro do limite diário). Usado pelo app para avisar antes de
    gerar as imagens, conforme pedido no briefing original.
    """
    total_imagens = n_blocos * imagens_por_bloco
    neurons_estimados = total_imagens * NEURONS_POR_IMAGEM
    return {
        "total_imagens": total_imagens,
        "neurons_estimados": neurons_estimados,
        "limite_gratuito_neurons_dia": LIMITE_GRATUITO_NEURONS_DIA,
        "dentro_do_limite_gratuito": neurons_estimados <= LIMITE_GRATUITO_NEURONS_DIA,
    }
