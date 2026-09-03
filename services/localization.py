"""Language selection and persisted text override loading."""

import datetime
import logging

import custom_texts
import texts as texts_module

logger = logging.getLogger(__name__)

user_language: dict[int | str, str] = {}


def get_user_lang(user_id: object) -> str:
    return user_language.get(user_id, "ar")


def tr(var_name: str, user_id: object) -> str:
    if get_user_lang(user_id) == "en":
        translated = texts_module.TEXTS_EN.get(var_name)
        if translated is not None:
            return translated
    return getattr(texts_module, var_name, "")


def load_custom_texts_into_memory() -> None:
    custom_list = custom_texts.list_custom()
    if not custom_list:
        logger.info("لا توجد نصوص مخصصة محفوظة حالياً")
        return

    logger.info("تم تحميل %s نص مخصص من JSON الدائم", len(custom_list))
    for var_name, entry in custom_list.items():
        value = entry.get("value", "")
        if var_name.startswith("EN::"):
            texts_module.TEXTS_EN[var_name.removeprefix("EN::")] = value
        else:
            setattr(texts_module, var_name, value)

        updated_at = entry.get("updated_at", 0)
        updated_text = (
            datetime.datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M:%S")
            if updated_at
            else "?"
        )
        logger.info(
            "نص %s (محرّر: %s، آخر تعديل: %s)",
            var_name,
            entry.get("editor_name", "Unknown"),
            updated_text,
        )
