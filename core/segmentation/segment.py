"""
Segmentação da transcrição em blocos narrativos/temáticos + geração do prompt
de cena (imagem) de cada bloco, via API do Google Gemini (tier gratuito).

Função pura: recebe o dicionário de transcrição (saída de
core/transcription/transcribe.py) e devolve uma lista de blocos. Não depende
de Streamlit nem de nenhuma outra camada de interface.

Requer a variável de ambiente GEMINI_API_KEY (ver README — seção "Chaves de
API"). Usamos o Gemini em vez da Anthropic aqui porque essa etapa (dividir
texto em blocos e escrever prompts de imagem) não exige o modelo mais caro
do mercado, e o tier gratuito do Gemini (aistudio.google.com) não pede
cartão de crédito — importante para um projeto paroquial sem orçamento.
"""

import logging
import os
import time

from dotenv import load_dotenv
from google.genai import types
from pydantic import BaseModel

from core.style import GUIA_ESTILO_VISUAL

load_dotenv()

logger = logging.getLogger("pascom.segmentacao")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

MODELO_PADRAO = "gemini-3.5-flash-lite"

INSTRUCOES_CHAVE_GEMINI = (
    "Chave GEMINI_API_KEY ausente ou inválida.\n"
    "Como conseguir uma (gratuito, sem cartão de crédito):\n"
    "1. Acesse https://aistudio.google.com/apikey e entre com uma conta Google.\n"
    "2. Clique em 'Create API key' (crie um projeto novo se pedir).\n"
    "3. Copie o valor gerado (começa com 'AIza').\n"
    "4. Cole esse valor em GEMINI_API_KEY no arquivo .env do projeto."
)


class ChaveApiAusenteError(Exception):
    """Levantado quando a chave do Gemini não está configurada, é inválida ou estourou a cota gratuita."""


class _BlocoLLM(BaseModel):
    id_segmento_inicio: int
    id_segmento_fim: int
    tema: str
    prompt_imagem: str


class _RespostaSegmentacao(BaseModel):
    blocos: list[_BlocoLLM]


def _montar_client():
    from google import genai

    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        raise ChaveApiAusenteError(INSTRUCOES_CHAVE_GEMINI)
    return genai.Client(api_key=chave)


def _montar_lista_segmentos(segmentos: list[dict]) -> str:
    linhas = [
        f"[{s['id']}] ({s['inicio']:.1f}s-{s['fim']:.1f}s): {s['texto']}"
        for s in segmentos
    ]
    return "\n".join(linhas)


SYSTEM_PROMPT_TEMPLATE = """\
Você é um diretor de arte trabalhando na produção de um vídeo devocional \
para a comunicação de uma paróquia católica, a partir da transcrição do \
Evangelho lido pelo padre.

Sua tarefa: dividir a transcrição abaixo (já segmentada com timestamps) em \
blocos narrativos/temáticos coerentes — cada bloco deve cobrir uma ideia ou \
cena da leitura. Gere entre {min_blocos} e {max_blocos} blocos, cobrindo TODA \
a transcrição, sem sobreposição e sem pular nenhum segmento.

Cada segmento de entrada tem um id numérico sequencial. Para cada bloco, \
informe apenas o id do primeiro e do último segmento que pertencem a ele \
(id_segmento_inicio e id_segmento_fim) — não invente timestamps, use só os \
ids fornecidos.

Para cada bloco, escreva também:
- "tema": um resumo curto (em português) do que está sendo narrado nesse \
bloco.
- "prompt_imagem": um prompt de geração de imagem em INGLÊS, descrevendo uma \
cena visual coerente com o texto do bloco, adequado para um modelo de \
imagem (Flux). O prompt deve sempre incorporar este guia de estilo fixo, \
para manter consistência visual entre todos os blocos do vídeo:

{guia_estilo}

Segmentos da transcrição:
{segmentos}
"""


def segment_transcript(
    transcricao: dict,
    model: str = MODELO_PADRAO,
    min_blocos: int = 3,
    max_blocos: int = 8,
) -> list[dict]:
    """
    Divide a transcrição em blocos temáticos e gera o prompt de imagem de
    cada um. Devolve uma lista de dicionários:

    [{"inicio": 0.0, "fim": 12.4, "texto": "...", "tema": "...", "prompt_imagem": "..."}, ...]

    Os timestamps de cada bloco vêm diretamente dos segmentos originais da
    transcrição (não são inventados pelo modelo), então sempre batem com o
    áudio.
    """
    segmentos = transcricao.get("segmentos") or []
    if not segmentos:
        raise ValueError("Transcrição sem segmentos — rode a transcrição antes da segmentação.")

    logger.info("Iniciando segmentação (%d segmentos de entrada, modelo=%s)...", len(segmentos), model)
    inicio = time.time()

    client = _montar_client()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        min_blocos=min_blocos,
        max_blocos=max_blocos,
        guia_estilo=GUIA_ESTILO_VISUAL,
        segmentos=_montar_lista_segmentos(segmentos),
    )

    try:
        resposta = client.models.generate_content(
            model=model,
            contents="Gere os blocos conforme instruído.",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=_RespostaSegmentacao,
            ),
        )
    except Exception as e:
        from google.genai import errors

        if isinstance(e, errors.ClientError):
            if e.code in (401, 403):
                raise ChaveApiAusenteError(INSTRUCOES_CHAVE_GEMINI) from e
            if e.code == 429:
                raise ChaveApiAusenteError(
                    "Cota gratuita do Gemini estourada por agora (limite por minuto/dia).\n"
                    "Aguarde alguns minutos e tente de novo, ou verifique os limites em "
                    "https://ai.google.dev/gemini-api/docs/rate-limits."
                ) from e
        raise

    if resposta.parsed is None:
        raise ValueError(f"O Gemini não devolveu um JSON válido no formato esperado. Resposta bruta: {resposta.text!r}")

    blocos_llm = resposta.parsed.blocos
    mapa_segmentos = {s["id"]: s for s in segmentos}
    ids_validos = sorted(mapa_segmentos.keys())

    blocos: list[dict] = []
    ids_esperado = ids_validos[0]
    for i, b in enumerate(blocos_llm):
        if b.id_segmento_inicio != ids_esperado:
            raise ValueError(
                f"Bloco {i}: esperava começar no segmento {ids_esperado}, "
                f"mas começou no {b.id_segmento_inicio} (blocos devem ser contíguos e cobrir tudo)."
            )
        if b.id_segmento_fim < b.id_segmento_inicio or b.id_segmento_fim not in mapa_segmentos:
            raise ValueError(f"Bloco {i}: intervalo de segmentos inválido ({b.id_segmento_inicio}-{b.id_segmento_fim}).")

        segs_do_bloco = [mapa_segmentos[j] for j in range(b.id_segmento_inicio, b.id_segmento_fim + 1)]
        blocos.append(
            {
                "inicio": segs_do_bloco[0]["inicio"],
                "fim": segs_do_bloco[-1]["fim"],
                "texto": " ".join(s["texto"] for s in segs_do_bloco),
                "tema": b.tema,
                "prompt_imagem": b.prompt_imagem,
            }
        )
        ids_esperado = b.id_segmento_fim + 1

    if ids_esperado - 1 != ids_validos[-1]:
        raise ValueError(
            f"Blocos não cobriram todos os segmentos (parou no {ids_esperado - 1}, "
            f"esperado até {ids_validos[-1]})."
        )

    logger.info(
        "Segmentação concluída em %.1fs — %d blocos gerados.",
        time.time() - inicio,
        len(blocos),
    )
    return blocos


def salvar_blocos_json(blocos: list[dict], output_path: str) -> None:
    """Salva a lista de blocos em um arquivo JSON legível (UTF-8, indentado)."""
    import json
    from pathlib import Path

    destino = Path(output_path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(blocos, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Blocos salvos em '%s'.", destino)
