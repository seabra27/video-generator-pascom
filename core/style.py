"""
Guia de estilo visual único, reaproveitado pela segmentação (para escrever os
prompts de cena) e pela geração de imagem (Fase 4), para manter a mesma
paleta e técnica em todas as imagens do vídeo.

Fica em inglês porque é embutido diretamente nos prompts de imagem enviados
ao modelo de geração (Flux, via fal.ai) — misturar português no meio de um
prompt em inglês prejudica a qualidade do resultado. A versão em português
abaixo é só para exibição na interface (revisão humana na Fase 6).
"""

GUIA_ESTILO_VISUAL = (
    "reverent oil painting, classic biblical illustration style, "
    "warm color palette (gold, terracotta, deep blue), "
    "soft directional lighting, visible brushstroke texture, "
    "serene and dignified composition, not photorealistic, "
    "no hyper-realistic depiction of Jesus's face — stylized, soft facial features, "
    "biblical-era setting (period-accurate clothing, architecture and landscape)"
)

GUIA_ESTILO_VISUAL_PT = (
    "Pintura a óleo reverente, estilo ilustração bíblica clássica, "
    "paleta de tons quentes (dourado, terracota, azul profundo), "
    "luz suave e direcional, textura de pincelada visível, "
    "composição serena e digna, sem fotorrealismo, "
    "sem rostos hiper-realistas de Jesus — rostos estilizados e suaves, "
    "ambientação da era bíblica (vestes, arquitetura e paisagem da época)."
)
