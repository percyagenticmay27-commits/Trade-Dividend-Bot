from src.dividend_bot.paper_cash_account import *  # noqa: F401,F403

if __name__ == "__main__":
    import os
    from src.dividend_bot.paper_cash_account import initialize_cash_account

    account = initialize_cash_account(
        investor_money=float(os.environ["DIVIDEND_INITIAL_PAPER_CASH"]) if os.environ.get("DIVIDEND_INITIAL_PAPER_CASH") else None,
        overwrite=os.environ.get("DIVIDEND_OVERWRITE_PAPER_CASH", "false").lower() == "true",
    )
    print(f"Paper cash account available balance: ${account['available_cash']:,.2f}")
