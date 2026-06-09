"""Local source: copy input/<name>_decl.json to output/<name>/."""
from pathlib import Path
from pipeline.decl import read_decl, write_decl


class LocalSource:
    def run(self, name: str) -> Path:
        src_path = Path("input") / f"{name}_decl.json"
        decl = read_decl(src_path)  # raises FileNotFoundError if missing
        out_path = Path("output") / name / f"{name}_decl.json"
        write_decl(decl, out_path)
        return out_path
