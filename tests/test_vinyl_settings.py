import config
from services.vinyl_settings import VinylSettings


def test_vinyl_settings_store_choice_and_rotation_per_context():
    settings = VinylSettings()
    context_key = "g-100:20"

    settings.set_choice(context_key, "pink")
    settings.set_rotation_value(context_key, "45")

    assert settings.get_choice(context_key) == "pink"
    assert settings.get_rotation_seconds(context_key) == 60 / 45

    settings.set_choice(context_key, "default")
    assert settings.get_choice(context_key) is None


def test_vinyl_settings_use_default_rotation():
    settings = VinylSettings()
    assert settings.get_rotation_seconds(1) == config.ROTATION_SECONDS
