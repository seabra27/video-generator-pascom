"""
App Streamlit — Pipeline de Vídeo do Evangelho (Pascom).

Orquestra os módulos de core/ (transcrição -> segmentação -> geração de
imagem -> montagem) numa interface passo a passo, pra quem não usa
terminal. Cada passo só aparece depois que o anterior termina, e o estado
de tudo (transcrição, blocos, imagens geradas, vídeo final) fica em
st.session_state pra sobreviver aos reruns do Streamlit a cada clique.

Rodar com: ./venv/Scripts/streamlit run app/main.py
"""

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core.assembly.assemble import montar_video
from core.image_generation.generate import estimar_uso, generate_images_for_block, salvar_imagem
from core.segmentation.segment import segment_transcript
from core.transcription.transcribe import FORMATOS_SUPORTADOS, transcribe_audio

N_VARIACOES_POR_BLOCO = 3
DIR_SAIDA_BASE = RAIZ / "output"

st.set_page_config(page_title="Vídeo do Evangelho — Pascom", page_icon="🎬", layout="centered")


def _erro_amigavel(e: Exception) -> str:
    """Formata a mensagem de erro pra markdown do Streamlit renderizar as quebras de linha."""
    return str(e).replace("\n", "  \n")


def _job_dir() -> Path:
    if "job_id" not in st.session_state:
        st.session_state.job_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = DIR_SAIDA_BASE / st.session_state.job_id
    destino.mkdir(parents=True, exist_ok=True)
    return destino


st.title("🎬 Vídeo do Evangelho")
st.caption(
    "Basílica Nossa Senhora de Lourdes, Vila Isabel — transforma o áudio do "
    "Evangelho dominical em um vídeo com imagens animadas sincronizadas."
)

if st.session_state.get("transcricao") is not None:
    if st.button("↺ Começar de novo (novo áudio)"):
        st.session_state.clear()
        st.rerun()

# --- Passo 1: upload + transcrição ---
st.header("1. Áudio do Evangelho")
arquivo = st.file_uploader(
    "Envie o áudio ou vídeo da leitura (ex: gravação do celular)",
    type=[ext.lstrip(".") for ext in sorted(FORMATOS_SUPORTADOS)],
    disabled="transcricao" in st.session_state,
)

if arquivo is not None and "transcricao" not in st.session_state:
    if st.button("Transcrever"):
        destino = _job_dir() / f"entrada{Path(arquivo.name).suffix.lower()}"
        destino.write_bytes(arquivo.getvalue())
        st.session_state.audio_path = str(destino)
        with st.spinner("Transcrevendo o áudio (pode levar alguns minutos)..."):
            try:
                st.session_state.transcricao = transcribe_audio(str(destino))
            except Exception as e:
                st.error(_erro_amigavel(e))

if "transcricao" in st.session_state:
    t = st.session_state.transcricao
    st.success(f"Transcrição concluída — {t['duracao_segundos']:.0f}s de áudio, {len(t['segmentos'])} trechos.")
    with st.expander("Ver texto transcrito"):
        st.write(t["texto_completo"])

# --- Passo 2: segmentação em blocos temáticos ---
if "transcricao" in st.session_state:
    st.header("2. Divisão em cenas")
    if st.button("Dividir em blocos", disabled="blocos" in st.session_state):
        with st.spinner("Dividindo a leitura em blocos temáticos (Google Gemini)..."):
            try:
                st.session_state.blocos = segment_transcript(st.session_state.transcricao)
            except Exception as e:
                st.error(_erro_amigavel(e))

if "blocos" in st.session_state:
    st.success(f"{len(st.session_state.blocos)} blocos identificados.")

# --- Passo 3: geração de imagem por bloco ---
if "blocos" in st.session_state:
    st.header("3. Imagens de cada cena")
    uso = estimar_uso(len(st.session_state.blocos), N_VARIACOES_POR_BLOCO)
    st.caption(
        f"Estimativa: até {uso['total_imagens']} imagens (~{uso['neurons_estimados']} "
        f"neurons Cloudflare de {uso['limite_gratuito_neurons_dia']}/dia gratuitos)."
    )

    for i, bloco in enumerate(st.session_state.blocos):
        st.subheader(f"Bloco {i + 1} — {bloco['tema']}")
        resumo_texto = bloco["texto"][:140] + ("…" if len(bloco["texto"]) > 140 else "")
        st.caption(f"{bloco['inicio']:.0f}s – {bloco['fim']:.0f}s · “{resumo_texto}”")

        chave_prompt = f"prompt_{i}"
        if chave_prompt not in st.session_state:
            st.session_state[chave_prompt] = bloco["prompt_imagem"]
        st.text_area("Prompt de imagem (em inglês)", key=chave_prompt, height=80)

        chave_candidatas = f"candidatas_{i}"
        rotulo_botao = "Gerar outras variações" if chave_candidatas in st.session_state else "Gerar variações"
        if st.button(rotulo_botao, key=f"gerar_{i}"):
            with st.spinner(f"Gerando {N_VARIACOES_POR_BLOCO} variações..."):
                try:
                    st.session_state[chave_candidatas] = generate_images_for_block(
                        st.session_state[chave_prompt], n_imagens=N_VARIACOES_POR_BLOCO
                    )
                    for j in range(N_VARIACOES_POR_BLOCO):
                        st.session_state.pop(f"usar_{i}_{j}", None)
                except Exception as e:
                    st.error(_erro_amigavel(e))

        if chave_candidatas in st.session_state:
            colunas = st.columns(N_VARIACOES_POR_BLOCO)
            for j, (coluna, imagem_bytes) in enumerate(zip(colunas, st.session_state[chave_candidatas])):
                with coluna:
                    st.image(imagem_bytes)
                    st.checkbox("Usar esta", key=f"usar_{i}_{j}", value=(j == 0))
            st.caption("Marque uma ou mais variações (várias = cross-fade suave entre elas nesse bloco).")

# --- Passo 4: montagem final ---
if "blocos" in st.session_state:
    st.header("4. Montar vídeo final")

    blocos_para_montar = []
    algum_bloco_incompleto = False
    for i, bloco in enumerate(st.session_state.blocos):
        chave_candidatas = f"candidatas_{i}"
        if chave_candidatas not in st.session_state:
            algum_bloco_incompleto = True
            continue
        selecionadas = [j for j in range(N_VARIACOES_POR_BLOCO) if st.session_state.get(f"usar_{i}_{j}")]
        if not selecionadas:
            algum_bloco_incompleto = True
            continue
        blocos_para_montar.append((i, bloco, selecionadas))

    if algum_bloco_incompleto:
        st.info("Gere e selecione ao menos uma imagem para cada bloco acima antes de montar o vídeo.")
    elif st.button("Montar vídeo", type="primary"):
        job_dir = _job_dir()
        imagens_dir = job_dir / "imagens"
        blocos_finais = []
        for i, bloco, selecionadas in blocos_para_montar:
            caminhos = []
            for j in selecionadas:
                destino = imagens_dir / f"bloco_{i}_img{j}.png"
                salvar_imagem(st.session_state[f"candidatas_{i}"][j], str(destino))
                caminhos.append(str(destino))
            blocos_finais.append({"inicio": bloco["inicio"], "fim": bloco["fim"], "imagens": caminhos})

        output_path = job_dir / "video_final.mp4"
        with st.spinner("Montando o vídeo final (isso pode levar alguns minutos)..."):
            try:
                montar_video(st.session_state.audio_path, blocos_finais, str(output_path))
                st.session_state.video_path = str(output_path)
            except Exception as e:
                st.error(_erro_amigavel(e))

if "video_path" in st.session_state:
    st.header("Vídeo pronto")
    st.video(st.session_state.video_path)
    with open(st.session_state.video_path, "rb") as f:
        st.download_button("⬇ Baixar vídeo", f, file_name="evangelho.mp4", mime="video/mp4")
