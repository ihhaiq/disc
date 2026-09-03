"""English user-facing strings."""

TEXTS_EN: dict[str, str] = {
    "MSG_START_HELP": (
        "<b>I'm making a vinyl Disc 💽🎶</b>\n\n"
        "💽 Send me an audio file that has a thumbnail, "
        "and I'll turn it into a spinning vinyl video note with your picture and sound 💽⚡️\n\n"
        "<b>🎶 Choose the disc rotation speed:</b>\n"
        "<i>This doesn't change the audio or file speed</i>"
    ),
    "MSG_CHOOSE_MODE": "📀 Got the file! Choose how you'd like your disc made:",
    "BTN_QUICK_CREATE": "⚡ Quick create",
    "BTN_CUSTOMIZE": "🎛 Customize",
    "MSG_WIZ_CHOOSE_COLOR": "🎨 Choose the disc color:",
    "MSG_WIZ_CHOOSE_SPEED": "🎚 Choose the rotation speed:",
    "MSG_WIZ_CHOOSE_IMAGE": (
        "🖼 Send the new cover image (replaces the current one if any),"
        "\nor tap skip to keep the original image."
    ),
    "BTN_WIZ_SKIP_IMAGE": "⏭ Skip (use original image)",
    "MSG_WIZ_NO_IMAGE_TO_SKIP": "⚠️ This file has no original image, you must send one.",
    "MSG_WIZ_CHOOSE_SEGMENT": "⏱ The file is longer than a minute, choose which minute to use:",
    "MSG_WIZ_STARTING": "🚀 Alright, creating your disc with the chosen settings...",
    "MSG_WIZ_EXPIRED": "⌛ Session expired, please send the file again.",
    "BTN_WIZ_SEGMENT_FMT": "⏱ Minute {n}",
    "MSG_QUICK_NEED_IMAGE": (
        "⚡ Quick create: this file has no thumbnail, send an image now and I'll continue automatically."
    ),
    "BTN_ADD_IMAGE": "➕ Add image",
    "BTN_CANCEL": "❌ Cancel",
    "BTN_VINYL_PINK": "💗  ",
    "BTN_VINYL_DEFAULT": "🔙 Use default",
    "BTN_VINYL_YELLOW": " 💛 ",
    "BTN_VINYL_BLUE": " 💙",
    "BTN_VINYL_SILVER": "🩶",
    "BTN_VINYL_COLOR_MENU": "🎨 Disc color",
    "BTN_VINYL_RED": "❤️",
    "BTN_VINYL_BLACK": " ",
    "BTN_VINYL_GREEN": "Green (beta)",
    "BTN_VINYL_BLOODY": "🩸",
    "BTN_VINYL_ROSE": "💮 ROSE",
    "BTN_VINYL_KOI": "  ",
    "BTN_VINYL_KISS": "KISS",
    "BTN_VINYL_ALI": "ALI",
    "BTN_BACK": "🔙 Back",
    "SPEED_LABEL_FULL": "Full turn",
    "SPEED_LABEL_8RPM": "8 RPM",
    "SPEED_LABEL_19RPM": "19 RPM",
    "SPEED_LABEL_33RPM": "33 RPM",
    "SPEED_LABEL_45RPM": "45 RPM",
    "MSG_VINYL_COLOR_INFO": (
        "🎨 Choose the disc color:\n"
        "⚫ Black\n"
        "💗 Pink\n"
        "🔵 Blue\n"
        "🟡 Yellow\n"
        "🟥 Bloody red"
    ),
    "MSG_WRONG_TYPE": "📌 Send an audio file, not a video or document, so its thumbnail is available.",
    "MSG_AUDIO_RECEIVED": (
        "⏳ Audio file received, converting it now. "
        "Only the first minute of the file will be used."
    ),
    "MSG_DURATION_TOO_LONG_FMT": (
        "⚠️ The file is longer than allowed! {duration:.0f} seconds. "
        "Maximum is one minute. "
        "I'll send you a one-minute video."
    ),
    "MSG_PROCESSING_ERROR_FMT": "❌ An error occurred while processing:\n<code>{error_text}</code>",
    "MSG_JOB_QUEUED": (
        "🧵 The file was added to the queue and will be processed once previous files are done. "
        "Only the first minute of the file will be used."
    ),
    "MSG_QUEUE_CANCELED_EDIT": "🗑️ Your pending jobs were canceled and your queue was cleared.",
    "MSG_QUEUE_CANCELED_ANSWER": "✅ Pending requests canceled",
    "MSG_QUEUE_POSITION_NEXT": "🔜 You're up next! Work on your request starts in a moment.",
    "MSG_QUEUE_POSITION_FMT": "📊 You're number {position} in the queue, we'll start once it's your turn.",
    "BTN_WIZ_PREVIEW": "🔍 Quick preview (3s)",
    "MSG_PREVIEW_STARTING": "🔍 Preparing a quick low-quality preview (3 seconds)...",
    "MSG_PREVIEW_READY_CAPTION": "🔍 This is a quick low-quality preview (3s) — the final version will be full quality.",
    "BTN_WIZ_CONFIRM_FULL": "🚀 Create the full video",
    "MSG_WIZ_REVIEW": "✅ All set! You can request a quick preview first, or create the full video right away.",
    "BTN_VINYL_COLOR_PREVIEW": "Preview",
    "MSG_SEND_IMAGE_NOW": "📷 Send me the image now and I'll use it with the audio file.",
    "MSG_NO_PENDING_AUDIO": "⚠️ No pending audio file linked to this image yet.",
    "MSG_AUDIO_EXPIRED": "⏰ The audio file wait time expired. Please send the audio file again.",
    "MSG_AUDIO_TOO_LARGE_FMT": (
        "❌ The file is larger than the allowed limit ({max_size_mb:.0f} MB). "
        "Send a smaller file and try again."
    ),
    "MSG_IMAGE_RECEIVED": (
        "✅ Image received, the bot will now start working on the audio file "
        "without needing to send it again."
    ),
    "MSG_DEV_ONLY_OPTION": "This option is for the developer only",
    "BTN_DEV_LIMITS_MENU": "🔒 Limits",
    "MSG_DEV_LIMITS_HEADER": (
        "🔒 Available discs:\n"
        "Tap any disc to toggle it between 🆓 Free and 💎 Paid.\n"
        "Paid discs only work for subscribers (or whitelist/developer)."
    ),
    "BTN_DEV_LIMITS_FREE_SUFFIX": "🆓",
    "BTN_DEV_LIMITS_PAID_SUFFIX": "💎",
    "MSG_DEV_LIMITS_TOGGLED_PAID_FMT": "💎 \"{name}\" is now a paid disc.",
    "MSG_DEV_LIMITS_TOGGLED_FREE_FMT": "🆓 \"{name}\" is now a free disc.",
    "MSG_COLOR_PREMIUM_ONLY": (
        "💎 This color is only available for paid subscribers.\n"
        "Tap the subscribe button on the main message to unlock it."
    ),
    "MSG_VINYL_CHOICE_SAVED_ANSWER": "✅ Choice saved",
    "MSG_SPEED_SAVED_ANSWER": "✅ Disc speed saved for this user",
    "STAGE_PREPARING": "Preparing",
    "STAGE_DOWNLOADING_AUDIO": "Downloading the audio file",
    "STAGE_DOWNLOADING_THUMBNAIL": "Downloading the cover image",
    "STAGE_BUILDING_DISC": "Building the disc design",
    "STAGE_RENDERING_VIDEO": "Rendering the video",
    "STAGE_UPLOADING_VIDEO": "Uploading and sending the video",
    "MSG_LIMIT_REACHED_FMT": (
        "🚫 You've reached the free daily limit ({limit} discs every 24 hours).\n"
        "⏳ Your limit resets in about {hours} hour(s).\n\n"
        "⭐ Or subscribe now and raise your daily limit to {premium_limit} discs/day "
        "for {price} Telegram Stars for 30 days."
    ),
    "BTN_BUY_STARS": "⭐ Subscribe {price} stars / 30 days",
    "MSG_PAYMENT_SUCCESS_FMT": (
        "✅ Subscription activated successfully!\n"
        "🔓 Your daily limit is now {limit} discs every 24 hours, for 30 days."
    ),
    "MSG_PAYMENT_INVALID": "❌ The payment details could not be verified. Subscription was not activated.",
    "MSG_PROCESSING_FAILED_SAFE": "The file could not be processed. Try another file or try again.",
    "BTN_LANG": "🇮🇶 العربية",
    "MSG_RICH_STATUS_INTRO": "I'm preparing a video for you. Please check the status later...",
    "BTN_DEV_SET_MENU_IMAGE": "🖼️ Change menu image",
    "BTN_VINYL_EMERALD": "EMERALD",
    "MSG_CHANNEL_ADMIN_ONLY": "🚫 This control is available to channel administrators only.",
    "MSG_CHANNEL_ASK_IMAGE_REPLY": "🖼 Reply to this message with the requested cover image.",
    "MSG_CHANNEL_ASK_IMAGE_REPLY_WITH_SKIP": (
        "🖼 Reply with a new cover image, or tap skip to keep the original image."
    ),
    "MSG_DEV_CHOOSE_TEMPLATE": "🎨 Choose a developer-only disc template:",
    "MSG_DEV_MENU_IMAGE_SAVED": "✅ Menu image saved.",
    "MSG_DEV_SEND_MENU_IMAGE": "🖼️ Send the image to display in the color menu:",
    "MSG_INVOICE_DESCRIPTION_FMT": (
        "Raises your daily creation limit to {limit} discs every 24 hours "
        "for 30 days from payment."
    ),
    "MSG_INVOICE_LABEL": "30-day subscription",
    "MSG_INVOICE_PAYLOAD_PREFIX": "sub",
    "MSG_INVOICE_TITLE": "30-day subscription — higher daily limit",
    "MSG_NEW_SUBSCRIBER_ADMIN_FMT": (
        "⭐ New subscription!\n\n"
        "👤 Name: {full_name}\n"
        "🔗 Username: {username}\n"
        "🆔 ID: {user_id}\n"
        "💰 Amount: {amount} Stars\n"
        "📅 Duration: {days} days\n"
        "🔓 New limit: {limit} discs/day"
    ),
    "MSG_PROCESSING_TIMEOUT_FMT": (
        "⏱️ Processing took longer than allowed ({minutes:.0f} minutes) and was canceled. "
        "Try a smaller file or try again."
    ),
}
