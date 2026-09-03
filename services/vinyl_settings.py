import config
from vinyl_catalog import get_vinyl_style


class VinylSettings:
    def __init__(self):
        self.rotation_seconds: dict[object, float | None] = {}
        self.vinyl_choice: dict[object, str] = {}

    def get_rotation_seconds(self, context_key) -> float | None:
        return self.rotation_seconds.get(context_key, config.ROTATION_SECONDS)

    def set_rotation_value(self, context_key, value: str) -> None:
        self.rotation_seconds[context_key] = 0.0 if value == "full" else 60 / float(value)

    def get_choice(self, context_key) -> str | None:
        return self.vinyl_choice.get(context_key)

    def set_choice(self, context_key, choice: str | None) -> None:
        if not choice or choice == "default":
            self.vinyl_choice.pop(context_key, None)
            return
        self.vinyl_choice[context_key] = choice

    def get_vinyl_path(self, context_key, choice_override: str | None = None) -> str:
        choice = choice_override if choice_override is not None else self.get_choice(context_key)
        return get_vinyl_style(choice).vinyl_path

    def get_shadow_path(self, context_key, choice_override: str | None = None) -> str:
        choice = choice_override if choice_override is not None else self.get_choice(context_key)
        return get_vinyl_style(choice).shadow_path

    @staticmethod
    def get_hole_ratio(vinyl_choice: str | None) -> float:
        return get_vinyl_style(vinyl_choice).hole_ratio_override or config.HOLE_RATIO
