#!/usr/bin/env python3
"""Gera as notas (Markdown) de uma release do Turnip S20 FE a partir do ambiente do workflow."""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

API = "https://gitlab.freedesktop.org/api/v4/projects/mesa%2Fmesa/repository/commits"
GENS = re.compile(r"\ba?([2-8])xx\b(?!\+)", re.I)
MAX_COMMITS = 300
MAX_PER_SECTION = 30

SECTIONS = [
    ("kgsl", "🔌 Kernel / KGSL", "comunicação com o driver de kernel da Qualcomm"),
    ("tu", "🧩 Turnip (Vulkan)", "implementação Vulkan do driver"),
    ("ir3", "⚙️ Compilador de shaders (ir3)", "compilação de shaders para a GPU"),
    ("autotune", "📈 Autotune", "escolha entre renderização GMEM e sysmem"),
    ("common", "🧱 Freedreno (A6xx e código comum)", "código compartilhado com o Adreno 650"),
]
NOISE = {"ci", "docs", "meson", "tools", "tests", "test", "decode", "afuc", "computerator",
         "cffdec", "cffdump", "rddecompiler", "replay", "crashdump", "deqp", "piglit"}


def gens(text):
    return {int(g) for g in GENS.findall(text)}


def classify(title):
    """Agrupa pelo título; outras gerações e infraestrutura saem do conteúdo principal."""
    pre = title.split(":", 1)[0].lower()
    parts = [x.strip() for x in re.split(r"[/,]", pre) if x.strip()]
    g = gens(pre) or gens(title)
    if g and 6 not in g:
        return "other"
    if "kgsl" in title.lower():
        return "kgsl"
    if "autotune" in pre:
        return "autotune"
    if set(parts) & NOISE or title.lower().startswith("uprev"):
        return "infra"
    if "ir3" in parts:
        return "ir3"
    if parts and parts[0] == "tu":
        return "tu"
    return "common"


def fetch_commits(sha, since):
    commits, page = [], 1
    while page and len(commits) < MAX_COMMITS:
        query = urllib.parse.urlencode({
            "ref_name": sha, "path": "src/freedreno",
            "since": since, "per_page": 100, "page": page,
        })
        try:
            with urllib.request.urlopen(f"{API}?{query}", timeout=30) as resp:
                commits += json.load(resp)
                nxt = resp.headers.get("X-Next-Page", "")
        except Exception as exc:  # rede ou API fora do ar
            print(f"aviso: changelog indisponível ({exc})", file=sys.stderr)
            return None
        page = int(nxt) if nxt.isdigit() else 0
    return commits[:MAX_COMMITS]


def patch_status():
    try:
        with open("applied-patches.diff", encoding="utf-8", errors="replace") as f:
            diff = f.read()
    except OSError:
        return None, None
    spirv = len(re.findall(r"^\+.*S20FE \*/", diff, re.M))
    return spirv, "S20FE_HOTPATH" in diff


def esc(text):
    return text.replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|")


def bullet(c):
    url = c.get("web_url") or f"https://gitlab.freedesktop.org/mesa/mesa/-/commit/{c['id']}"
    return f"- [`{c['short_id'][:8]}`]({url}) {esc(c['title'])}"


def build_notes(env, commits):
    e = env.get
    nightly = e("CHANNEL", "stable") == "nightly"
    sha = e("MESA_SHA", "")
    short = sha[:10]
    since = (e("SINCE") or "").strip()
    zip_name = e("ZIP_NAME", "Turnip-S20FE.zip")
    commits_url = f"https://gitlab.freedesktop.org/mesa/mesa/-/commits/{sha}/src/freedreno"

    spirv, hotpath = patch_status()
    if hotpath is None:
        patch_txt = "⚠️ não verificado"
    elif not hotpath:
        patch_txt = "⚠️ não aplicado"
    else:
        patch_txt = "✅ aplicado" + (f" (+ {spirv} chamada(s) SPIR-V)" if spirv else "")

    out = []
    if nightly:
        out.append("> 🌙 **Nightly.** Build automático do Mesa `main`, publicado como pré-release. "
                   "Se algo não funcionar bem, volte para a versão anterior.")
    else:
        out.append("> ✅ **Estável.** Build promovido manualmente pelo mantenedor.")
    out += ["", "## 🔧 Turnip para Galaxy S20 FE 5G", "",
            "Driver Vulkan open source (Mesa Turnip) compilado e ajustado para o "
            "**Snapdragon 865 / Adreno 650**.", ""]

    items = [h.strip() for h in re.split(r"[;\n]", e("HIGHLIGHTS", "")) if h.strip()]
    if items:
        out += ["## ✨ Destaques", ""] + [f"- {esc(h)}" for h in items] + [""]

    rows = [
        ("Dispositivo", "Galaxy S20 FE 5G · Snapdragon 865 · Adreno 650"),
        ("Mesa", f"`{e('MESA_VER', '?')}` · [`{short}`](https://gitlab.freedesktop.org/mesa/mesa/-/commit/{sha}) · {e('MESA_DATE', '?')}"),
        ("Canal", "nightly (pré-release)" if nightly else "estável"),
        ("Compilação", f"Clang (NDK {e('NDK_VERSION', '?')}) · API {e('ANDROID_API', '?')} · -{e('OPT_LEVEL', 'O3')} · FMA · sem LTO"),
        ("Patch SELinux (anti-spam no logcat)", patch_txt),
        ("TU_DEBUG embutido", f"`{e('TU_DBG', 'none')}`"),
        ("SHA-256 (libvulkan_freedreno.so)", f"`{e('SHA256', '?')}`"),
    ]
    out += ["| Item | Detalhe |", "| --- | --- |"] + [f"| {a} | {b} |" for a, b in rows] + [""]

    out += ["## 📥 Como instalar", "",
            f"1. Baixe **`{zip_name}`** em *Assets* (não precisa extrair).",
            "2. No app (Winlator, GameNative, GameHub, Eden…), abra o gerenciador de drivers e importe o ZIP.",
            "3. Para voltar atrás, selecione o driver anterior no mesmo menu.", ""]

    out += ["## 🔄 O que mudou no Mesa", ""]
    if not since:
        out.append("_Primeira release deste canal: não há base de comparação._")
    elif commits is None:
        out.append("_Lista de mudanças indisponível nesta execução._")
    elif not commits:
        out.append(f"Nenhum commit em `src/freedreno` desde {since[:10]}.")
    else:
        groups = {}
        for c in commits:
            groups.setdefault(classify(c["title"]), []).append(c)
        n_other = len(groups.get("other", []))
        n_infra = len(groups.get("infra", []))
        n_rel = len(commits) - n_other - n_infra
        limit = " (limitado aos mais recentes)" if len(commits) >= MAX_COMMITS else ""
        out += [f"Desde **{since[:10]}**: {len(commits)} commits em `src/freedreno`{limit} · "
                f"**{n_rel}** relevantes · {n_other} de outras gerações · {n_infra} de infraestrutura. "
                f"[Ver no GitLab]({commits_url})", ""]
        names = [lbl for k, lbl, _ in SECTIONS if groups.get(k)]
        if n_rel:
            out += ["**Resumo:** mudanças em " + ", ".join(x.split(" ", 1)[1] for x in names) + ".", ""]
        else:
            out += ["**Resumo:** nenhuma mudança direta no Adreno 650 nesta atualização.", ""]
        for key, label, desc in SECTIONS:
            items = groups.get(key, [])
            if not items:
                continue
            out += [f"### {label} ({len(items)})", "", f"_{desc}_", ""]
            out += [bullet(c) for c in items[:MAX_PER_SECTION]]
            if len(items) > MAX_PER_SECTION:
                out.append(f"- … e mais {len(items) - MAX_PER_SECTION}")
            out.append("")
        for key, title in (("other", "Outras gerações (a3xx–a5xx, a7xx+): não se aplicam ao Adreno 650"),
                           ("infra", "Infraestrutura (CI, docs, ferramentas): não alteram o driver")):
            lst = groups.get(key, [])
            if lst:
                out += [f"<details><summary>{title} — {len(lst)}</summary>", ""]
                out += [bullet(c) for c in lst[:MAX_PER_SECTION]]
                if len(lst) > MAX_PER_SECTION:
                    out.append(f"- … e mais {len(lst) - MAX_PER_SECTION}")
                out += ["", "</details>", ""]

    run_url = e("RUN_URL", "")
    footer = f"[GitHub Actions]({run_url})" if run_url else "GitHub Actions"
    out += ["", "---", "", f"<sub>Gerado automaticamente por {footer}.</sub>"]
    return "\n".join(out) + "\n"


def main():
    since = (os.environ.get("SINCE") or "").strip()
    commits = fetch_commits(os.environ.get("MESA_SHA", "main"), since) if since else []
    sys.stdout.write(build_notes(os.environ, commits))


if __name__ == "__main__":
    main()
