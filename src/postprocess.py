# src/postprocess.py
"""
Sanitização de saídas de LLM.

Problema observado na execução anterior: todos os artefatos (plan.json,
analysis_findings.json, patch.sql, RCA_report.md) foram gravados envoltos em
cercas markdown (```json ... ```), tornando os JSONs inválidos e o SQL
inexecutável. Este módulo remove as cercas, valida o schema mínimo de cada
artefato e reescreve o arquivo já limpo.

É chamado como callback de cada Task do CrewAI (ver src/crew.py), de modo que
o pipeline nunca deixa um artefato malformado em reports/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FENCE_RE = re.compile(
    r"^\s*```[a-zA-Z0-9_+-]*\s*\n(?P<body>.*?)\n?\s*```\s*$",
    re.DOTALL,
)


def strip_fences(text: str) -> str:
    """Remove cercas markdown externas, se houver. Idempotente."""
    if text is None:
        return ""
    out = text.strip()
    # remove cercas repetidas (LLM às vezes aninha)
    for _ in range(3):
        m = FENCE_RE.match(out)
        if not m:
            break
        out = m.group("body").strip()
    return out


def extract_json(text: str) -> Any:
    """
    Extrai o primeiro objeto/array JSON válido do texto.
    Levanta ValueError se não encontrar nada parseável.
    """
    cleaned = strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # fallback: recorta do primeiro '{' ou '[' até o fechamento balanceado
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start : i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError("Nenhum JSON válido encontrado na saída do agente.")


# ---------------------------------------------------------------------------
# Schemas mínimos por artefato (chaves obrigatórias no nível raiz)
# ---------------------------------------------------------------------------
REQUIRED_KEYS = {
    "reports/plan.json": ["tasks"],
    "reports/analysis_findings.json": ["findings", "notes"],
    "reports/validation_report.json": ["syntax_ok", "blocked_commands", "before_after"],
}

# Chaves obrigatórias dentro de cada item de "findings"
FINDING_KEYS = ["problem", "evidence", "business_impact", "priority"]


class SchemaError(ValueError):
    pass


def _check_schema(path: str, data: Any) -> list[str]:
    """Retorna lista de violações (vazia = OK)."""
    problems: list[str] = []
    required = REQUIRED_KEYS.get(path, [])
    if required and not isinstance(data, dict):
        return [f"{path}: raiz deveria ser objeto JSON, veio {type(data).__name__}"]
    for key in required:
        if key not in data:
            problems.append(f"{path}: chave obrigatória ausente -> '{key}'")

    if path.endswith("analysis_findings.json") and isinstance(data, dict):
        findings = data.get("findings")
        if not isinstance(findings, list) or not findings:
            problems.append(f"{path}: 'findings' deve ser lista não-vazia")
        else:
            for i, f in enumerate(findings):
                if not isinstance(f, dict):
                    problems.append(f"{path}: findings[{i}] não é objeto")
                    continue
                for key in FINDING_KEYS:
                    if key not in f:
                        problems.append(
                            f"{path}: findings[{i}] sem chave obrigatória '{key}'"
                        )
    return problems


def sanitize_json_artifact(path: str, strict: bool = False) -> dict:
    """
    Lê o arquivo, remove cercas, valida schema e regrava JSON indentado.
    Retorna {"ok": bool, "problems": [...], "path": path}.
    Com strict=True, levanta SchemaError em caso de violação.
    """
    p = Path(path)
    if not p.exists():
        return {"ok": False, "problems": [f"{path}: arquivo não gerado"], "path": path}

    raw = p.read_text(encoding="utf-8")
    try:
        data = extract_json(raw)
    except ValueError as e:
        result = {"ok": False, "problems": [f"{path}: {e}"], "path": path}
        if strict:
            raise SchemaError(result["problems"][0])
        return result

    problems = _check_schema(path, data)
    p.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if problems and strict:
        raise SchemaError("; ".join(problems))
    return {"ok": not problems, "problems": problems, "path": path}


def sanitize_text_artifact(path: str) -> dict:
    """Remove cercas de artefatos textuais (patch.sql, RCA_report.md)."""
    p = Path(path)
    if not p.exists():
        return {"ok": False, "problems": [f"{path}: arquivo não gerado"], "path": path}
    cleaned = strip_fences(p.read_text(encoding="utf-8"))
    if not cleaned.strip():
        return {"ok": False, "problems": [f"{path}: conteúdo vazio"], "path": path}
    p.write_text(cleaned + "\n", encoding="utf-8")
    return {"ok": True, "problems": [], "path": path}


def sanitize(path: str, strict: bool = False) -> dict:
    """Despacha por extensão."""
    if path.endswith(".json"):
        return sanitize_json_artifact(path, strict=strict)
    return sanitize_text_artifact(path)


def make_task_callback(path: str, strict: bool = False):
    """Fábrica de callbacks para Task(callback=...) do CrewAI."""

    def _cb(_output=None):
        res = sanitize(path, strict=strict)
        status = "ok" if res["ok"] else "PROBLEMAS"
        print(f"[postprocess] {path}: {status}")
        for prob in res["problems"]:
            print(f"[postprocess]   - {prob}")
        return res

    return _cb


if __name__ == "__main__":
    import sys

    targets = sys.argv[1:] or [
        "reports/plan.json",
        "reports/analysis_findings.json",
        "reports/patch.sql",
        "reports/validation_report.json",
        "reports/RCA_report.md",
    ]
    for t in targets:
        print(json.dumps(sanitize(t), ensure_ascii=False))
