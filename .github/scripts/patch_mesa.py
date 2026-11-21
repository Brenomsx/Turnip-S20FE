#!/usr/bin/env python3
"""Aplica os patches do Turnip S20 FE na árvore do Mesa (rode dentro da pasta mesa/)."""
import os
import pathlib
import re
import sys

tu_dbg = os.environ.get("TU_DBG", "none").strip() or "none"


def read(p):
    return p.read_text(encoding="utf-8", errors="replace")


# 1) SPIR-V: remove leitura de MESA_SPIRV_DUMP_PATH / MESA_SPIRV_READ_PATH
spirv_n = 0
p = pathlib.Path("src/compiler/spirv/spirv_to_nir.c")
if p.is_file():
    s = read(p)
    s, spirv_n = re.subn(r'os_get_option\s*\(\s*"MESA_SPIRV_(?:DUMP|READ)_PATH"\s*\)',
                         "NULL /* S20FE */", s)
    if spirv_n:
        p.write_text(s, encoding="utf-8")
print(f"SPIR-V: {spirv_n} chamada(s) neutralizada(s)")
if not spirv_n:
    print("::notice::Padrão SPIR-V não encontrado; o hotpath cobre essas leituras. Ocorrências atuais:")
    for d in ("src/compiler/spirv", "src/util"):
        for f in sorted(pathlib.Path(d).rglob("*.c")):
            for i, line in enumerate(read(f).splitlines(), 1):
                if "MESA_SPIRV" in line:
                    print(f"   {f}:{i}: {line.strip()}")

# 2) Hotpath: propriedades Android com SPIRV/IR3/TRACE retornam NULL (evita spam SELinux)
hot = False
p = pathlib.Path("src/util/os_misc.c")
if p.is_file():
    s = read(p)
    if "S20FE_HOTPATH" in s:
        hot = True
    else:
        m = re.search(r'\bos_get_android_option\s*\(\s*const\s+char\s*\*\s*(\w+)\s*\)\s*\{', s)
        if m:
            a = m.group(1)
            ins = (f'\n   /* S20FE_HOTPATH */\n'
                   f'   if (strstr({a}, "SPIRV") || strstr({a}, "IR3") || strstr({a}, "TRACE"))\n'
                   f'      return NULL;\n')
            p.write_text(s[:m.end()] + ins + s[m.end():], encoding="utf-8")
            hot = True
print(f"Hotpath: {'aplicado' if hot else 'NÃO aplicado'}")

# 3) TU_DEBUG embutido (opcional)
if tu_dbg != "none":
    done = False
    for p in sorted(pathlib.Path("src/freedreno/vulkan").rglob("tu_device.*")):
        if p.suffix not in (".c", ".cc", ".cpp"):
            continue
        s = read(p)
        m = re.search(r'\btu_CreateInstance\s*\([^)]*\)\s*\{', s)
        if m and "S20FE_TU_DEBUG" not in s:
            # Junta com o TU_DEBUG que o app já definiu (ex.: noconform) em vez de ser ignorado.
            ins = (f'\n   /* S20FE_TU_DEBUG */\n'
                   f'   {{\n'
                   f'      const char *s20fe_old = getenv("TU_DEBUG");\n'
                   f'      char s20fe_buf[256];\n'
                   f'      snprintf(s20fe_buf, sizeof(s20fe_buf), "%s%s{tu_dbg}",\n'
                   f'               s20fe_old ? s20fe_old : "", (s20fe_old && *s20fe_old) ? "," : "");\n'
                   f'      setenv("TU_DEBUG", s20fe_buf, 1);\n'
                   f'   }}\n')
            inc = re.search(r'^#include\b', s, re.M)
            head = "#include <stdio.h>\n#include <stdlib.h>\n"
            body = s[:m.end()] + ins + s[m.end():]
            if inc:
                body = body[:inc.start()] + head + body[inc.start():]
            p.write_text(body, encoding="utf-8")
            print(f"TU_DEBUG={tu_dbg} em {p}")
            done = True
            break
    if not done:
        print(f"::warning::TU_DEBUG={tu_dbg} pedido, mas tu_CreateInstance não foi encontrada.")

# O hotpath é o patch essencial: sem ele o driver gera spam de SELinux/travamento. Falha alto.
if not hot:
    print("::error::Hotpath (os_get_android_option) não aplicado: a base do Mesa mudou. "
          "Ajuste .github/scripts/patch_mesa.py.")
    sys.exit(1)
