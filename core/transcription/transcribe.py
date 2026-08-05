"""
Transcrição local de áudio com timestamps, usando faster-whisper (CTranslate2).

Não depende de nenhuma chave de API — o modelo roda inteiramente na máquina.
Função pura: recebe o caminho de um áudio e devolve um dicionário com o
texto e os timestamps por segmento (e, opcionalmente, por palavra).

Formatos aceitos: .opus, .ogg, .m4a, .mp3, .wav, .mov, .mp4 (qualquer formato
que o PyAV/FFmpeg conheça, na prática — inclusive vídeos, dos quais só a
trilha de áudio é extraída). O faster-whisper decodifica o áudio via
PyAV, que já embute as bibliotecas do FFmpeg — não é necessário ffmpeg no
sistema só para esta etapa. Ainda assim, o ffmpeg do sistema é exigido pela
Fase 5 (montagem do vídeo), então o setup do projeto já garante que ele
esteja instalado.
"""

import logging
import time
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

logger = logging.getLogger("pascom.transcricao")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

FORMATOS_SUPORTADOS = {".opus", ".ogg", ".m4a", ".mp3", ".wav", ".mov", ".mp4"}

# Cache do modelo em memória: recarregar o modelo a cada chamada seria lento
# (alguns segundos) e desnecessário quando várias transcrições ocorrem na
# mesma sessão do app.
_modelo_carregado: dict[str, WhisperModel] = {}


def _obter_modelo(model_size: str, device: str, compute_type: str) -> WhisperModel:
    chave = f"{model_size}:{device}:{compute_type}"
    if chave not in _modelo_carregado:
        logger.info("Carregando modelo Whisper '%s' (device=%s, compute_type=%s)...", model_size, device, compute_type)
        inicio = time.time()
        _modelo_carregado[chave] = WhisperModel(model_size, device=device, compute_type=compute_type)
        logger.info("Modelo carregado em %.1fs.", time.time() - inicio)
    return _modelo_carregado[chave]


def transcribe_audio(
    audio_path: str,
    model_size: str = "small",
    language: str = "pt",
    device: str = "cpu",
    compute_type: str = "int8",
    word_timestamps: bool = True,
) -> dict:
    """
    Transcreve um arquivo de áudio e devolve um dicionário estruturado:

    {
        "idioma": "pt",
        "duracao_segundos": 172.4,
        "texto_completo": "...",
        "segmentos": [
            {
                "id": 0,
                "inicio": 0.0,
                "fim": 4.2,
                "texto": "Naquele tempo, Jesus disse aos seus discípulos...",
                "palavras": [
                    {"palavra": "Naquele", "inicio": 0.0, "fim": 0.4, "probabilidade": 0.98},
                    ...
                ]
            },
            ...
        ]
    }

    Levanta FileNotFoundError se o áudio não existir, e ValueError se a
    extensão não for reconhecida (para pegar erros de upload cedo, com
    mensagem clara, em vez de deixar o erro estourar lá dentro do FFmpeg).
    """
    caminho = Path(audio_path)
    if not caminho.exists():
        raise FileNotFoundError(f"Áudio não encontrado: {audio_path}")
    if caminho.suffix.lower() not in FORMATOS_SUPORTADOS:
        raise ValueError(
            f"Formato '{caminho.suffix}' não suportado. "
            f"Formatos aceitos: {', '.join(sorted(FORMATOS_SUPORTADOS))}"
        )

    logger.info("Iniciando transcrição de '%s'...", caminho.name)
    inicio = time.time()

    modelo = _obter_modelo(model_size, device, compute_type)
    segments, info = modelo.transcribe(
        str(caminho),
        language=language,
        word_timestamps=word_timestamps,
    )

    segmentos = []
    partes_texto = []
    for i, seg in enumerate(segments):
        texto_segmento = seg.text.strip()
        partes_texto.append(texto_segmento)

        palavras = None
        if word_timestamps and seg.words:
            palavras = [
                {
                    "palavra": w.word.strip(),
                    "inicio": round(w.start, 2),
                    "fim": round(w.end, 2),
                    "probabilidade": round(w.probability, 3),
                }
                for w in seg.words
            ]

        segmentos.append(
            {
                "id": i,
                "inicio": round(seg.start, 2),
                "fim": round(seg.end, 2),
                "texto": texto_segmento,
                "palavras": palavras,
            }
        )

    duracao_transcricao = time.time() - inicio
    logger.info(
        "Transcrição concluída em %.1fs — %d segmentos, %.1fs de áudio (idioma detectado: %s, confiança: %.0f%%).",
        duracao_transcricao,
        len(segmentos),
        info.duration,
        info.language,
        info.language_probability * 100,
    )

    return {
        "idioma": info.language,
        "duracao_segundos": round(info.duration, 2),
        "texto_completo": " ".join(partes_texto),
        "segmentos": segmentos,
    }


def salvar_transcricao_json(transcricao: dict, output_path: str) -> None:
    """Salva o dicionário de transcrição em um arquivo JSON legível (UTF-8, indentado)."""
    import json

    destino = Path(output_path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(transcricao, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Transcrição salva em '%s'.", destino)
