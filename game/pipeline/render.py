"""Render resolved JSON into HTML viewers using jinja2 templates."""
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

HTML_DIR = Path(__file__).parent / "html"
COLORS = {"S": "#1a5276", "G": "#27ae60", "O": "#e67e22",
          "R": "#2ecc71", "r": "#f39c12", "L": "#6a9fb5"}
LEGEND = [
    ("S", "海"), ("G", "绿地"), ("O", "红地"),
    ("R", "绿路"), ("r", "红路"),
]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(HTML_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _legend_html() -> str:
    return "".join(
        f'<div class="li"><span class="lc" style="background:{COLORS[ch]}"></span>{ch}={label}</div>'
        for ch, label in LEGEND
    )


def _world_legend_html() -> str:
    parts = [_legend_html(),
             '<div class="li"><span class="lc" style="background:#6a9fb5"></span>📍 城市</div>']
    return "".join(parts)


def generate_map_html(resolved: dict, output_path: str) -> None:
    env = _env()
    template = env.get_template("map_viewer.html.j2")
    html = template.render(
        name=resolved["name"],
        legend_html=_legend_html(),
        colors_js=json.dumps(COLORS),
    )
    Path(output_path).write_text(html, encoding="utf-8")


def generate_world_html(resolved: dict, output_path: str) -> None:
    env = _env()
    template = env.get_template("world_viewer.html.j2")
    html = template.render(
        resolved=resolved,
        resolved_json=json.dumps(resolved, ensure_ascii=False),
        legend_html=_world_legend_html(),
    )
    Path(output_path).write_text(html, encoding="utf-8")
