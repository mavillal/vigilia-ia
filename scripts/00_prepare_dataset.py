#!/usr/bin/env python3
"""
00_prepare_dataset.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Paso DATA del pipeline (Anexo D, Figura D.1).
Prepara y valida el dataset de entrenamiento YOLOv8 a partir del CSV maestro
(vigilia_dataset_entrenamiento_completo.csv) y las imágenes 4K de Copper Phoenix I.

Input : CSV maestro + imágenes 4K (3840x2160 px)
Output: Estructura images/labels/train/val + vigilia_dataset.yaml

Dataset de referencia (Copper Phoenix I — Anexo C):
  - Total: 1.720 imágenes (1.200 sintéticas + 520 nativas)
  - mineral_normal : 760 imgs (480 sintéticas + 280 nativas)
  - roca_oversize  : 560 imgs (420 sintéticas + 140 nativas)
  - metal_grande   : 400 imgs (300 sintéticas + 100 nativas)
  - Split: 80/20 train/val · Formato YOLOv8 TXT · Resolución 3840x2160 px

Uso:
  python 00_prepare_dataset.py \
    --csv ./data/vigilia_dataset_entrenamiento_completo.csv \
    --images ./data/raw_images \
    --output ./data \
    --split 0.8
"""

import argparse
import csv
import json
import logging
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("prepare_dataset")

# Clases operacionales VIGIL-IA (Anexo C, Figura C.3)
CLASS_MAP = {0: "mineral_normal", 1: "roca_oversize", 2: "metal_grande"}
CLASS_NAME_TO_ID = {v: k for k, v in CLASS_MAP.items()}

EXPECTED_COLUMNS = {"image_filename", "class_id", "origin", "cx", "cy", "width", "height"}


def parse_args():
    p = argparse.ArgumentParser(description="Preparación y validación del dataset VIGIL-IA (YOLOv8)")
    p.add_argument("--csv", required=True, help="CSV maestro con anotaciones (vigilia_dataset_entrenamiento_completo.csv)")
    p.add_argument("--images", required=True, help="Directorio con imágenes 4K crudas")
    p.add_argument("--output", default="./data", help="Directorio de salida (default: ./data)")
    p.add_argument("--split", type=float, default=0.8, help="Fracción de train (default: 0.8, i.e. 80/20)")
    p.add_argument("--seed", type=int, default=42, help="Semilla para split reproducible")
    p.add_argument("--copy", action="store_true", help="Copiar imágenes en vez de crear symlinks")
    return p.parse_args()


def load_master_csv(csv_path: Path):
    """Lee el CSV maestro y agrupa anotaciones por imagen. No inventa filas faltantes."""
    if not csv_path.exists():
        log.error(f"CSV maestro no encontrado: {csv_path}")
        sys.exit(1)

    annotations = defaultdict(list)
    origins = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = EXPECTED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            log.error(f"El CSV no contiene las columnas esperadas: {missing}")
            sys.exit(1)

        for row in reader:
            fname = row["image_filename"].strip()
            class_id = int(row["class_id"])
            if class_id not in CLASS_MAP:
                log.warning(f"class_id desconocido ({class_id}) en {fname}, se omite fila")
                continue
            annotations[fname].append(
                (class_id, float(row["cx"]), float(row["cy"]), float(row["width"]), float(row["height"]))
            )
            origins[fname] = row.get("origin", "unknown").strip().lower()

    log.info(f"CSV cargado: {len(annotations)} imágenes con anotaciones")
    return annotations, origins


def validate_images(annotations, origins, images_dir: Path):
    """Verifica que cada imagen referenciada exista físicamente. Reporta faltantes sin inventar datos."""
    valid, missing = [], []
    for fname in annotations:
        if (images_dir / fname).exists():
            valid.append(fname)
        else:
            missing.append(fname)

    if missing:
        log.warning(f"{len(missing)} imágenes referenciadas en el CSV no se encontraron en {images_dir}")
        for m in missing[:10]:
            log.warning(f"  - faltante: {m}")
        if len(missing) > 10:
            log.warning(f"  ... y {len(missing) - 10} más")

    log.info(f"Imágenes válidas: {len(valid)} / {len(annotations)}")
    return valid


def stratified_split(valid_files, annotations, split_ratio, seed):
    """Split 80/20 estratificado por clase dominante de cada imagen."""
    random.seed(seed)
    by_class = defaultdict(list)
    for fname in valid_files:
        classes_in_img = [a[0] for a in annotations[fname]]
        dominant_class = max(set(classes_in_img), key=classes_in_img.count)
        by_class[dominant_class].append(fname)

    train_set, val_set = [], []
    for class_id, files in by_class.items():
        random.shuffle(files)
        cut = int(len(files) * split_ratio)
        train_set.extend(files[:cut])
        val_set.extend(files[cut:])
        log.info(f"  clase {CLASS_MAP[class_id]}: {len(files)} imgs -> train={cut}, val={len(files) - cut}")

    random.shuffle(train_set)
    random.shuffle(val_set)
    return train_set, val_set


def write_split(files, annotations, images_dir, out_images_dir, out_labels_dir, copy_mode):
    out_images_dir.mkdir(parents=True, exist_ok=True)
    out_labels_dir.mkdir(parents=True, exist_ok=True)

    for fname in files:
        src_img = images_dir / fname
        dst_img = out_images_dir / fname
        if dst_img.exists():
            dst_img.unlink()
        if copy_mode:
            shutil.copy2(src_img, dst_img)
        else:
            try:
                dst_img.symlink_to(src_img.resolve())
            except OSError:
                shutil.copy2(src_img, dst_img)

        label_path = out_labels_dir / (Path(fname).stem + ".txt")
        with open(label_path, "w") as lf:
            for class_id, cx, cy, w, h in annotations[fname]:
                lf.write(f"{class_id} {cx:.4f} {cy:.4f} {w:.4f} {h:.4f}\n")


def write_dataset_yaml(output_dir: Path):
    yaml_path = output_dir / "vigilia_dataset.yaml"
    content = (
        f"# vigilia_dataset.yaml — generado por 00_prepare_dataset.py\n"
        f"path: {output_dir.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n"
        f"  0: {CLASS_MAP[0]}\n"
        f"  1: {CLASS_MAP[1]}\n"
        f"  2: {CLASS_MAP[2]}\n"
    )
    yaml_path.write_text(content)
    log.info(f"vigilia_dataset.yaml escrito en {yaml_path}")
    return yaml_path


def main():
    args = parse_args()
    csv_path = Path(args.csv)
    images_dir = Path(args.images)
    output_dir = Path(args.output)

    log.info("=== VIGIL-IA · 00_prepare_dataset.py ===")
    annotations, origins = load_master_csv(csv_path)
    valid_files = validate_images(annotations, origins, images_dir)

    if not valid_files:
        log.error("No hay imágenes válidas para procesar. Abortando.")
        sys.exit(1)

    log.info(f"Split estratificado por clase ({int(args.split*100)}/{int((1-args.split)*100)}):")
    train_files, val_files = stratified_split(valid_files, annotations, args.split, args.seed)

    write_split(train_files, annotations, images_dir, output_dir / "images/train", output_dir / "labels/train", args.copy)
    write_split(val_files, annotations, images_dir, output_dir / "images/val", output_dir / "labels/val", args.copy)
    yaml_path = write_dataset_yaml(output_dir)

    summary = {
        "total_imagenes": len(valid_files),
        "imagenes_faltantes": len(annotations) - len(valid_files),
        "train": len(train_files),
        "val": len(val_files),
        "split_ratio": args.split,
        "clases": CLASS_MAP,
        "dataset_yaml": str(yaml_path),
    }
    summary_path = output_dir / "dataset_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    log.info(f"Resumen guardado en {summary_path}")
    log.info("Dataset preparado correctamente.")


if __name__ == "__main__":
    main()
