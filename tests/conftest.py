import os


# config.py intentionally refuses to boot without a token. Tests use a syntactically
# valid placeholder so they remain hermetic and never depend on a developer's .env.
os.environ.setdefault("BOT_TOKEN", "123456:test-token")
