"""Compatibility entry point for the enterprise HTML dashboard generator."""
from src.dividend_bot.enterprise_html_dashboard import *  # noqa: F401,F403

if __name__ == "__main__":
    result = build_html_portal()
    print(f"AI CIO portal generated: {result['index_path']}")
