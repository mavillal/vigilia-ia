#!/usr/bin/env python3
"""
scripts/validate_dataset_manifest.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Valida que el dataset documentado en data/DATASET_SPEC.md (versión
machine-readable: data/dataset_manifest.json) sea consistente con:

  1. Su propia aritmética interna (las cifras por clase deben sumar a los
     totales declarados).
  2. Las constantes de negocio del código (backend/constants.py):
     CLASS_MAP (ids y nombres de clase) y DEPLOY_CONF_THRESHOLDS (umbrales
     de confianza en producción) deben coincidir exactamente.
  3. (Opcional, si existe) El dataset realmente preparado por
     00_prepare_dataset.py (data/dataset_summary.json) — un desvío aquí NO
     es necesariamente un error: el proyecto contempla ampliar el
     subconjunto nativo en iteraciones futuras. Se reporta como advertencia
     para que DATASET_SPEC.md se actualice a propósito, no por deriva
     silenciosa.

Uso:
  python scripts/validate_dataset_manifest.py
  python scripts/validate_dataset_manifest.py --dataset_summary ./data/dataset_summary.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("validate_dataset_manifest")

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "dataset_manifest.json"
BACKEND_CONSTANTS = REPO_ROOT / "backend" / "constants.py"

sys.path.insert(0, str(REPO_ROOT / "backend"))


def parse_args():
    p = argparse.ArgumentParser(description="Validación del manifiesto del dataset VIGIL-IA")
    p.add_argument("--manifest", default=str(MANIFEST_PATH))
    p.add_argument(
        "--dataset_summary",
        default=str(REPO_ROOT / "data" / "dataset_summary.json"),
        help="Salida real de 00_prepare_dataset.py, si ya se ejecutó (opcional)",
    )
    return p.parse_args()


def check_manifest_arithmetic(manifest: dict) -> list:
    log.info("=== 1. Aritmética interna del manifiesto ===")
    failures = []
    clases = manifest["clases"]
    totales = manifest["totales"]

    suma_total = sum(c["total_imgs"] for c in clases.values())
    suma_sinteticas = sum(c["sinteticas"] for c in clases.values())
    suma_nativas = sum(c["nativas"] for c in clases.values())

    checks = [
        ("total_imgs", suma_total, totales["total_imgs"]),
        ("sinteticas", suma_sinteticas, totales["sinteticas"]),
        ("nativas", suma_nativas, totales["nativas"]),
    ]
    for nombre, calculado, declarado in checks:
        if calculado != declarado:
            failures.append(f"{nombre}: suma por clase ({calculado}) != total declarado ({declarado})")
        else:
            log.info(f"  {nombre}: OK ({calculado})")

    for clase, datos in clases.items():
        if datos["sinteticas"] + datos["nativas"] != datos["total_imgs"]:
            failures.append(
                f"{clase}: sinteticas + nativas ({datos['sinteticas']}+{datos['nativas']}) "
                f"!= total_imgs ({datos['total_imgs']})"
            )
        else:
            log.info(f"  {clase}: sinteticas + nativas == total_imgs OK")

    pct_sum = sum(c["porcentaje_dataset"] for c in clases.values())
    if abs(pct_sum - 100.0) > 0.2:
        failures.append(f"Los porcentajes por clase suman {pct_sum}%, se esperaba ~100%")
    else:
        log.info(f"  porcentajes por clase: OK (suman {pct_sum}%)")

    return failures


def check_manifest_vs_code(manifest: dict) -> list:
    log.info("=== 2. Manifiesto vs. constantes de negocio (backend/constants.py) ===")
    failures = []

    if not BACKEND_CONSTANTS.exists():
        return ["No se encontró backend/constants.py"]

    from constants import CLASS_MAP, DEPLOY_CONF_THRESHOLDS  # noqa: E402

    manifest_class_ids = {datos["class_id"]: nombre for nombre, datos in manifest["clases"].items()}
    if manifest_class_ids != CLASS_MAP:
        failures.append(f"CLASS_MAP difiere: manifiesto={manifest_class_ids} vs código={CLASS_MAP}")
    else:
        log.info(f"  CLASS_MAP: OK ({CLASS_MAP})")

    for clase, datos in manifest["clases"].items():
        umbral_manifiesto = datos["umbral_confianza_deploy"]
        umbral_codigo = DEPLOY_CONF_THRESHOLDS.get(clase)
        if umbral_manifiesto != umbral_codigo:
            failures.append(
                f"{clase}: umbral_confianza_deploy del manifiesto ({umbral_manifiesto}) "
                f"!= DEPLOY_CONF_THRESHOLDS del código ({umbral_codigo})"
            )
        else:
            log.info(f"  {clase}: umbral de confianza deploy OK ({umbral_codigo})")

    return failures


def check_manifest_vs_real_dataset(manifest: dict, summary_path: Path) -> list:
    log.info("=== 3. Manifiesto vs. dataset realmente preparado (informativo) ===")
    if not summary_path.exists():
        log.info(f"  {summary_path} no existe todavía (normal si 00_prepare_dataset.py no ha corrido). Se omite.")
        return []

    summary = json.loads(summary_path.read_text())
    total_real = summary.get("total_imagenes")
    total_manifiesto = manifest["totales"]["total_imgs"]

    if total_real is None:
        log.warning("  dataset_summary.json no tiene 'total_imagenes'; se omite la comparación.")
        return []

    if total_real != total_manifiesto:
        log.warning(
            f"  El dataset real preparado tiene {total_real} imágenes; "
            f"DATASET_SPEC.md/manifest documentan {total_manifiesto}. "
            f"Si el cambio es intencional (ej. ampliación del subconjunto nativo), "
            f"actualizar data/DATASET_SPEC.md y data/dataset_manifest.json en el mismo commit."
        )
    else:
        log.info(f"  Dataset real ({total_real} imágenes) coincide con el manifiesto documentado.")

    return []  # informativo: nunca hace fallar la validación


def main():
    args = parse_args()
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        log.error(f"No se encontró el manifiesto: {manifest_path}")
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text())

    failures = []
    failures += check_manifest_arithmetic(manifest)
    failures += check_manifest_vs_code(manifest)
    failures += check_manifest_vs_real_dataset(manifest, Path(args.dataset_summary))

    if failures:
        log.error("=== Inconsistencias detectadas ===")
        for f in failures:
            log.error(f"  - {f}")
        sys.exit(1)

    log.info("Manifiesto del dataset consistente con el código y consigo mismo.")


if __name__ == "__main__":
    main()
