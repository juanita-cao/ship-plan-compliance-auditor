from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from src.frontend.view_models import ResultsViewModel
from src.viz import render_spotlight

logger = logging.getLogger(__name__)


def render_spotlight_node(
    vm: ResultsViewModel,
    selected_category: str | None = None,
    selected_instance_id: str | None = None,
) -> Image.Image:
    try:
        return render_spotlight(
            Path(vm.image_path),
            vm.instances,
            selected_category=selected_category,
            selected_instance_id=selected_instance_id,
        )
    except Exception as exc:
        logger.warning("F-Spotlight: render failed (%s), returning original image", exc)
        try:
            return Image.open(vm.image_path).convert("RGB")
        except Exception:
            return Image.new("RGB", (400, 300), (40, 40, 40))
