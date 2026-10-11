# core/config.py
# উদ্দেশ্য: প্রজেক্টের সমস্ত পরিবেশ ভেরিয়েবল ও গ্লোবাল কনফিগারেশন লোড করা

import os
from pathlib import Path
from dotenv import load_dotenv

# প্রজেক্ট রুট পাথ চিহ্নিত করা
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

# Compatibility aliases for legacy modules. New orchestration code reads the
# provider-neutral settings above; these remain only for an explicit
# AI_PROVIDER=gemini migration fallback.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
APP_API_KEY = os.getenv("APP_API_KEY", "default-insecure-key")
