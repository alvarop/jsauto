"""Install the bundled Claude Code skill into ~/.claude/skills/."""

import os
import shutil
import sys
from importlib.resources import files


def install_skill(target_dir: str | None = None) -> None:
    if target_dir is None:
        target_dir = os.path.expanduser("~/.claude/skills/joulescope")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, "SKILL.md")
    skill_ref = files("js_automation").joinpath("data/SKILL.md")
    with skill_ref.open("rb") as src:
        content = src.read()
    with open(target_path, "wb") as dst:
        dst.write(content)
    print(f"Skill installed: {target_path}")
    print("Restart Claude Code (or reload skills) to pick it up.")
