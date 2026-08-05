"""
Montagem do vídeo final: aplica efeito Ken Burns (zoom/pan lento) sobre as
imagens de cada bloco, sincronizado com o áudio original.

Função pura, sem dependência de interface: recebe o caminho do áudio e uma
lista de blocos (cada um com "inicio", "fim" e uma lista de caminhos de
imagem já salvos em disco) e escreve o vídeo final em output_path.

Não precisa de nenhuma chave de API — roda 100% local via FFmpeg/MoviePy.
Precisa do ffmpeg instalado no sistema (ver README — Fase 2).

Versão desta fase: Ken Burns simples, uma imagem por bloco (zoom lento
centralizado). Cross-fade entre múltiplas imagens por bloco e parallax em
camadas vêm depois, só depois de validar esta versão ponta a ponta.
"""

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, VideoClip, concatenate_audioclips, concatenate_videoclips
from PIL import Image

logger = logging.getLogger("pascom.montagem")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

RESOLUCAO_PADRAO = (1920, 1080)  # 16:9
ZOOM_FINAL_PADRAO = 1.15  # a imagem termina 15% mais "zoomada" que no início
FPS_PADRAO = 24
PRESET_ENCODE_PADRAO = "veryfast"  # velocidade de encode do x264; "medium" (padrão do ffmpeg) é bem mais lento


def _extrair_audio_limpo(caminho_original: str) -> str:
    """
    Extrai o áudio para um .wav temporário via ffmpeg direto (subprocess),
    em vez de deixar o MoviePy ler o arquivo original.

    Necessário porque o parser de metadados do MoviePy quebra com certos
    arquivos de vídeo (ex: .MOV gravado por iPhone, que traz metadados
    extras da Apple tipo geolocalização e Dolby Vision) — extrair direto
    evita esse problema, e de quebra normaliza o áudio antes da montagem.
    """
    destino = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(
        ["ffmpeg", "-y", "-i", caminho_original, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", destino],
        check=True,
        capture_output=True,
    )
    return destino


def _carregar_imagem_cover(caminho_imagem: str, resolucao: tuple[int, int]) -> np.ndarray:
    """
    Carrega a imagem e já redimensiona/corta pra cobrir exatamente o quadro
    de saída ("cover"), UMA ÚNICA VEZ (com PIL, fora do MoviePy). Isso evita
    que o MoviePy tenha que refazer esse resize em todo frame do vídeo — só
    sobra o resize dinâmico do zoom, o que corta bastante o tempo de render.
    """
    largura_saida, altura_saida = resolucao
    img = Image.open(caminho_imagem).convert("RGB")

    fator = max(largura_saida / img.width, altura_saida / img.height)
    nova_largura = round(img.width * fator) + 2
    nova_altura = round(img.height * fator) + 2
    img = img.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)

    esquerda = (nova_largura - largura_saida) // 2
    topo = (nova_altura - altura_saida) // 2
    img = img.crop((esquerda, topo, esquerda + largura_saida, topo + altura_saida))
    return np.array(img)


def _clip_ken_burns(caminho_imagem: str, duracao: float, resolucao: tuple[int, int], zoom_final: float) -> VideoClip:
    """
    Devolve um clipe com zoom lento e centralizado sobre a imagem, cortado
    para o tamanho de saída (resolucao).

    Implementado como uma função de frame customizada (em vez de encadear
    os efeitos `.resized()` + `.cropped()`/`CompositeVideoClip` do MoviePy)
    por dois motivos:
    1. Velocidade: o `CompositeVideoClip` (pensado pra sobrepor vários
       clipes) é ~2.6x mais lento aqui do que simplesmente recortar a
       imagem já redimensionada.
    2. Corretude: o `.cropped()` do MoviePy calcula a janela de corte UMA
       VEZ (usando `clip.w`/`clip.h`, que refletem o tamanho ANTES do
       zoom), mas a imagem cresce a cada frame — isso faz o corte derivar
       pro canto superior esquerdo em vez de ficar centralizado. Fazendo o
       resize+corte manualmente a cada frame (com base no tamanho real da
       imagem naquele instante) evita esse problema.
    """
    largura_saida, altura_saida = resolucao
    array_base = _carregar_imagem_cover(caminho_imagem, resolucao)
    imagem_base = Image.fromarray(array_base)

    def frame_no_tempo(t):
        progresso = t / duracao if duracao > 0 else 0
        escala = 1 + (zoom_final - 1) * progresso
        nova_largura = round(largura_saida * escala)
        nova_altura = round(altura_saida * escala)
        imagem_grande = imagem_base.resize((nova_largura, nova_altura), Image.Resampling.LANCZOS)
        esquerda = (nova_largura - largura_saida) // 2
        topo = (nova_altura - altura_saida) // 2
        imagem_cortada = imagem_grande.crop((esquerda, topo, esquerda + largura_saida, topo + altura_saida))
        return np.array(imagem_cortada)

    return VideoClip(frame_function=frame_no_tempo, duration=duracao)


def montar_video_simples(
    audio_path: str,
    blocos: list[dict],
    output_path: str,
    resolucao: tuple[int, int] = RESOLUCAO_PADRAO,
    zoom_final: float = ZOOM_FINAL_PADRAO,
    fps: int = FPS_PADRAO,
) -> None:
    """
    Monta o vídeo com Ken Burns simples: uma imagem por bloco, com zoom
    lento, exibida do início ao fim do bloco (usando os timestamps reais
    vindos da transcrição/segmentação), sincronizada com o áudio original.

    Cada bloco em `blocos` precisa ter: "inicio" (float, segundos),
    "fim" (float, segundos) e "imagens" (list[str], caminhos de arquivo —
    usamos só a primeira nesta versão simples).
    """
    if not blocos:
        raise ValueError("Lista de blocos vazia — rode a segmentação antes da montagem.")

    logger.info("Iniciando montagem do vídeo (%d blocos, resolução %dx%d)...", len(blocos), *resolucao)
    inicio_processo = time.time()

    audio_limpo = _extrair_audio_limpo(audio_path)
    audio = AudioFileClip(audio_limpo)

    clipes_video = []
    clipes_audio = []
    for i, bloco in enumerate(blocos):
        imagens = bloco.get("imagens") or []
        if not imagens:
            raise ValueError(f"Bloco {i} não tem nenhuma imagem gerada.")

        duracao = bloco["fim"] - bloco["inicio"]
        if duracao <= 0:
            raise ValueError(f"Bloco {i} tem duração inválida ({duracao}s).")

        clipes_video.append(_clip_ken_burns(imagens[0], duracao, resolucao, zoom_final))
        # Recorta o áudio exatamente no mesmo intervalo [inicio, fim] do bloco —
        # não dá pra simplesmente pegar os primeiros N segundos do áudio original,
        # porque as pausas entre frases não aparecem no vídeo (os blocos ficam
        # colados um no outro), e isso desincronizaria áudio e imagem a partir
        # do segundo bloco em diante.
        clipes_audio.append(audio.subclipped(bloco["inicio"], bloco["fim"]))
        logger.info("Bloco %d/%d preparado (%.1fs, imagem: %s).", i + 1, len(blocos), duracao, Path(imagens[0]).name)

    video = concatenate_videoclips(clipes_video, method="chain")
    audio_sincronizado = concatenate_audioclips(clipes_audio)
    video = video.with_audio(audio_sincronizado)

    destino = Path(output_path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(destino),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset=PRESET_ENCODE_PADRAO,
        threads=os.cpu_count(),
        logger=None,
    )

    logger.info(
        "Vídeo montado em %.1fs — duração final %.1fs, salvo em '%s'.",
        time.time() - inicio_processo,
        video.duration,
        destino,
    )
