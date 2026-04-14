"""Model information document rendering and export helpers."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
import textwrap
import zipfile

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from backend.init_db import EXPORTS_DIRECTORY


def build_model_report_data(version: dict) -> dict:
    """Normalize one model version into report-friendly sections."""
    evaluation = version.get("latest_evaluation") or {}
    overall = evaluation.get("overall_metrics") or {}
    per_class = evaluation.get("per_class_metrics") or []
    family_name = str(version.get("family_name") or version.get("name") or "")
    version_tag = str(version.get("version_tag") or "")
    training_name = str(version.get("training_dataset_name") or "-")
    test_name = str(version.get("test_dataset_name") or "-")
    return {
        "title": f"{family_name} {version_tag}".strip(),
        "family_name": family_name,
        "version_tag": version_tag,
        "original_file_name": str(version.get("original_file_name") or "-"),
        "stored_model_path": str(version.get("model_file_name") or "-"),
        "description": str(version.get("description") or "").strip(),
        "training_dataset": {
            "name": training_name,
            "images_dir": str(version.get("training_images_dir") or "-"),
            "labels_dir": str(version.get("training_labels_dir") or "-"),
            "description": str(version.get("training_dataset_description") or "").strip(),
        },
        "test_dataset": {
            "name": test_name,
            "images_dir": str(version.get("test_images_dir") or "-"),
            "labels_dir": str(version.get("test_labels_dir") or "-"),
            "description": str(version.get("test_dataset_description") or "").strip(),
        },
        "evaluation": {
            "created_at": str(evaluation.get("created_at") or ""),
            "score_threshold": evaluation.get("score_threshold"),
            "overall_metrics": overall,
            "per_class_metrics": per_class,
            "summary_text": str(evaluation.get("summary_text") or "").strip(),
        },
        "created_at": str(version.get("created_at") or ""),
        "notes": str(version.get("notes") or "").strip(),
    }


def render_model_report_html(report: dict) -> str:
    """Create a readable standalone HTML document for one model version."""
    metric_lines = _build_metric_lines(report)
    metrics_html = "".join(
        [
            (
                "<div class='metric-line'>"
                f"<div class='metric-line-title'>{escape(line['title'])}</div>"
                f"<div class='metric-line-values'>{''.join(_metric_chip(label, value) for label, value in line['values'])}</div>"
                "</div>"
            )
            for line in metric_lines
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{escape(report["title"])}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 36px; color: #172112; }}
    h1, h2 {{ margin-bottom: 8px; }}
    h1 {{ font-size: 28px; }}
    h2 {{ font-size: 18px; margin-top: 28px; border-bottom: 1px solid #d9e1d2; padding-bottom: 6px; }}
    p {{ line-height: 1.7; font-size: 16px; }}
    .muted {{ color: #54614f; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #d9e1d2; border-radius: 12px; padding: 14px; background: #f8fbf5; }}
    .metric-lines {{ display: grid; gap: 14px; }}
    .metric-line {{ border: 1px solid #d9e1d2; border-radius: 12px; padding: 16px; background: #ffffff; }}
    .metric-line-title {{ font-size: 13px; color: #54614f; text-transform: uppercase; margin-bottom: 10px; }}
    .metric-line-values {{ display: flex; flex-wrap: wrap; gap: 12px; }}
    .metric-chip {{ border: 1px solid #d9e1d2; border-radius: 10px; padding: 10px 12px; min-width: 170px; background: #f8fbf5; }}
    .metric-chip-label {{ font-size: 12px; color: #54614f; text-transform: uppercase; }}
    .metric-chip-value {{ font-size: 28px; font-weight: bold; margin-top: 4px; }}
    .prewrap {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>{escape(report["title"])}</h1>
  <p class="muted">Model file: {escape(report["original_file_name"])} | Created: {escape(_format_date(report["created_at"]))}</p>

  <h2>Description</h2>
  <p class="prewrap">{escape(report["description"] or "No description provided.")}</p>

  <h2>Datasets</h2>
  <div class="grid">
    <div class="card">
      <h3>Training Dataset</h3>
      <p><strong>Name:</strong> {escape(report["training_dataset"]["name"])}</p>
      <p><strong>Images:</strong> {escape(report["training_dataset"]["images_dir"])}</p>
      <p><strong>Labels:</strong> {escape(report["training_dataset"]["labels_dir"])}</p>
      <p class="prewrap">{escape(report["training_dataset"]["description"] or "No dataset description provided.")}</p>
    </div>
    <div class="card">
      <h3>Test Dataset</h3>
      <p><strong>Name:</strong> {escape(report["test_dataset"]["name"])}</p>
      <p><strong>Images:</strong> {escape(report["test_dataset"]["images_dir"])}</p>
      <p><strong>Labels:</strong> {escape(report["test_dataset"]["labels_dir"])}</p>
      <p class="prewrap">{escape(report["test_dataset"]["description"] or "No dataset description provided.")}</p>
    </div>
  </div>

  <h2>Evaluation Summary</h2>
  <div class="metric-lines">{metrics_html}</div>
  <p class="muted">Threshold: {escape(str(report["evaluation"]["score_threshold"]))} | Evaluated: {escape(_format_date(report["evaluation"]["created_at"]))}</p>
  <p class="prewrap">{escape(report["evaluation"]["summary_text"] or "No evaluation summary stored yet.")}</p>

  <h2>Storage</h2>
  <p><strong>Stored checkpoint:</strong> {escape(report["stored_model_path"])}</p>
  <p class="prewrap">{escape(report["notes"] or "No additional notes stored.")}</p>
</body>
</html>"""


def generate_model_report_pdf(report: dict) -> Path:
    """Generate a simple multi-page PDF report for one model version."""
    EXPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_file_name(report["title"]) or "model_report"
    pdf_path = EXPORTS_DIRECTORY / f"{safe_name}.pdf"

    lines = _build_pdf_lines(report)
    font = ImageFont.load_default()
    page_width = 1240
    page_height = 1754
    margin = 72
    line_height = 24
    max_width_chars = 100
    max_lines_per_page = max(1, (page_height - (margin * 2)) // line_height)

    wrapped_lines: list[str] = []
    for line in lines:
        if not line:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(textwrap.wrap(line, width=max_width_chars) or [""])

    pages: list[Image.Image] = []
    for start in range(0, len(wrapped_lines), max_lines_per_page):
        page = Image.new("RGB", (page_width, page_height), color="white")
        draw = ImageDraw.Draw(page)
        y = margin
        for line in wrapped_lines[start:start + max_lines_per_page]:
            draw.text((margin, y), line, fill="black", font=font)
            y += line_height
        pages.append(page)

    if not pages:
        pages = [Image.new("RGB", (page_width, page_height), color="white")]

    first_page, remaining_pages = pages[0], pages[1:]
    first_page.save(pdf_path, "PDF", resolution=150.0, save_all=True, append_images=remaining_pages)
    return pdf_path.resolve()


def create_model_export_zip(report: dict, model_file_path: str) -> Path:
    """Bundle the checkpoint and generated HTML document into one export zip."""
    EXPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    title = report["title"] or "model_export"
    zip_path = EXPORTS_DIRECTORY / f"{_safe_file_name(title)}.zip"
    model_path = Path(model_file_path).expanduser().resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(model_path, arcname=model_path.name)
        zip_file.writestr("model_information.html", render_model_report_html(report).encode("utf-8"))
    return zip_path.resolve()


def _build_pdf_lines(report: dict) -> list[str]:
    metric_lines = _build_metric_lines(report)
    lines = [
        report["title"],
        "",
        f"Created: {_format_date(report['created_at'])}",
        f"Original file: {report['original_file_name']}",
        f"Stored checkpoint: {report['stored_model_path']}",
        "",
        "Description",
        report["description"] or "No description provided.",
        "",
        "Training Dataset",
        f"Name: {report['training_dataset']['name']}",
        f"Images: {report['training_dataset']['images_dir']}",
        f"Labels: {report['training_dataset']['labels_dir']}",
        report["training_dataset"]["description"] or "No dataset description provided.",
        "",
        "Test Dataset",
        f"Name: {report['test_dataset']['name']}",
        f"Images: {report['test_dataset']['images_dir']}",
        f"Labels: {report['test_dataset']['labels_dir']}",
        report["test_dataset"]["description"] or "No dataset description provided.",
        "",
        "Overall Evaluation",
    ]
    for line in metric_lines:
        lines.append(line["title"])
        for label, value in line["values"]:
            lines.append(f"{label}: {value}")
        lines.append("")
    lines.extend([
        f"Threshold: {report['evaluation']['score_threshold']}",
        f"Evaluated: {_format_date(report['evaluation']['created_at'])}",
        report["evaluation"]["summary_text"] or "No evaluation summary stored yet.",
    ])
    if report["notes"]:
        lines.extend(["", "Notes", report["notes"]])
    return lines


def _format_metric(value) -> str:
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _format_date(raw_value: str) -> str:
    if not raw_value:
        return "-"
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw_value


def _safe_file_name(value: str) -> str:
    normalized = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)
    return normalized.strip("_")


def _metric_chip(label: str, value: str) -> str:
    return (
        "<div class='metric-chip'>"
        f"<div class='metric-chip-label'>{escape(label)}</div>"
        f"<div class='metric-chip-value'>{escape(value)}</div>"
        "</div>"
    )


def _build_requested_metrics(report: dict) -> dict[str, str]:
    overall = report["evaluation"]["overall_metrics"]
    per_class_rows = report["evaluation"]["per_class_metrics"]
    per_class_lookup = {
        str(row.get("class_name") or "").strip().lower(): row
        for row in per_class_rows
    }
    dead_row = per_class_lookup.get("dead", {})
    live_row = per_class_lookup.get("live", {})
    return {
        "overall_map": _format_metric(overall.get("map")),
        "map_50": _format_metric(overall.get("map_50")),
        "map_75": _format_metric(overall.get("map_75")),
        "dead_precision": _format_metric(dead_row.get("precision")),
        "dead_recall": _format_metric(dead_row.get("recall")),
        "alive_precision": _format_metric(live_row.get("precision")),
        "alive_recall": _format_metric(live_row.get("recall")),
    }


def _build_metric_lines(report: dict) -> list[dict[str, object]]:
    metrics = _build_requested_metrics(report)
    return [
        {
            "title": "mAP Values",
            "values": [
                ("Overall mAP", metrics["overall_map"]),
                ("mAP@50", metrics["map_50"]),
                ("mAP@75", metrics["map_75"]),
            ],
        },
        {
            "title": "Dead Class",
            "values": [
                ("Precision", metrics["dead_precision"]),
                ("Recall", metrics["dead_recall"]),
            ],
        },
        {
            "title": "Alive Class",
            "values": [
                ("Precision", metrics["alive_precision"]),
                ("Recall", metrics["alive_recall"]),
            ],
        },
    ]
