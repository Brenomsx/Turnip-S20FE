# Turnip S20 FE

Driver Vulkan **Mesa Turnip** compilado e ajustado para o **Galaxy S20 FE 5G (Snapdragon 865 / Adreno 650)**, atualizado automaticamente.

## Downloads
Em [Releases](https://github.com/Brenomsx/Turnip-S20FE/releases):

| Canal | O que é |
| --- | --- |
| **Nightly** (pré-release) | Build automático do Mesa `main`, toda segunda-feira se houver novidade. Mantém os 5 mais recentes. |
| **Estável** | Build promovido manualmente. |

## Instalação
Baixe o ZIP, importe no gerenciador de drivers do app (Winlator, GameNative, GameHub, Eden…) e, para voltar atrás, selecione o driver anterior.

## Como funciona
- `auto-update.yml` roda às segundas, 09:00 UTC (05:00 em Boa Vista), compara o Mesa `main` com a última release e dispara `build.yml` se houver commit novo.
- Cada release traz o que mudou no `src/freedreno`, separado por área.
- Se um build nightly falhar, abre uma Issue "Build nightly falhou"; ela fecha sozinha quando um build voltar a passar.
- `patch_mesa.py` aplica os ajustes contra spam de SELinux; o build falha de propósito se o patch essencial não casar com o Mesa.

## Publicar uma versão estável
Actions → *Build Turnip* → Run workflow: `channel = stable`, `publish_release = true`, destaques separados por `;`.

## Observações
- Nightlies acompanham o Mesa `main` e podem regredir.
- Repositórios públicos sem atividade por 60 dias têm agendamentos desativados; um commit qualquer reativa.

Baseado no [Mesa 3D](https://mesa3d.org).
