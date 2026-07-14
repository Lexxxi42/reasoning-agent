import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

import requests
from langchain_core.tools import tool

DATA_PATH = Path(__file__).parent / "data" / "obligations.json"

def _load_obligations() -> list[dict]:
    """Читает и парсит JSON-фикстуру с диска"""
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Файл с данными не найден: {DATA_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Некорректный JSON в файле {DATA_PATH}: {exc}") from exc


def _date_in_range(
    date_str: str, start_date: Optional[str], end_date: Optional[str]
) -> bool:
    date = datetime.fromisoformat(date_str)
    if start_date and date < datetime.fromisoformat(start_date):
        return False
    if end_date and date > datetime.fromisoformat(end_date):
        return False
    return True


@tool
def get_obligations(
    status: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    Возвращает список финансовых обязательств пользователя (подписки, платежи,
    коммунальные услуги и т.д.) из локальной базы.

    Args:
        status: Фильтр по статусу ('active', 'canceled'). Если не указан — все статусы.
        category: Фильтр по категории ('subscription', 'utility', 'housing', 'lifestyle').
                  Если не указан — все категории.
        start_date: Начало диапазона по дате следующего списания, YYYY-MM-DD.
                    Используй, когда нужно посчитать траты "в ближайшие N дней" или
                    "на этой неделе" — start_date обычно равен сегодняшней дате.
        end_date: Конец диапазона по дате следующего списания, YYYY-MM-DD.
    """
    try:
        data = _load_obligations()
    except RuntimeError as exc:
        return f"Ошибка: {exc}"

    result = data
    if status:
        result = [item for item in result if item.get("status") == status]
    if category:
        result = [item for item in result if item.get("category") == category]
    if start_date or end_date:
        try:
            result = [
                item
                for item in result
                if _date_in_range(item["next_payment_date"], start_date, end_date)
            ]
        except (KeyError, ValueError) as exc:
            return f"Ошибка при фильтрации по дате: {exc}"

    return json.dumps(result, ensure_ascii=False)


@tool
def calculate_total_spending(
    target_currency: str = "RUB",
    category: Optional[str] = None,
    status: Optional[str] = "active",
) -> str:
    """
    Вычисляет общую сумму расходов по подпискам, конвертируя все в целевую валюту.
    Это инструмент желателен для ответа на вопросы «сколько всего потрачено» —
    используй его вместо вызова get_obligations + множественных convert_currency.

    Args:
        target_currency: Валюта для итога (по умолчанию RUB).
        category: Фильтр по категории (опционально).
        status: Фильтр по статусу (по умолчанию 'active', только активные платежи).
    """
    obligations = get_obligations.invoke({"category": category, "status": status})
    if isinstance(obligations, str):  # ошибка
        return json.dumps({"error": obligations})

    total = 0.0
    currency_breakdown = {}
    conversion_errors = []

    for item in obligations:
        amount = item["amount"]
        currency = item["currency"]

        if currency == target_currency:
            converted = amount
        else:
            result_str = convert_currency.invoke(
                {
                    "amount": amount,
                    "from_currency": currency,
                    "to_currency": target_currency,
                }
            )
            result = json.loads(result_str)
            if "error" in result:
                conversion_errors.append(
                    f"{item['title']}: {result['error']}"
                )
                continue
            converted = result.get("converted_amount", 0)

        total += converted
        if currency not in currency_breakdown:
            currency_breakdown[currency] = 0
        currency_breakdown[currency] += converted

    return json.dumps(
        {
            "total_amount": round(total, 2),
            "target_currency": target_currency,
            "items_count": len(obligations),
            "currency_breakdown": {k: round(v, 2) for k, v in currency_breakdown.items()},
            "conversion_errors": conversion_errors,
        }
    )


@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Конвертирует сумму из одной валюты в другую по актуальному курсу через
    публичный API frankfurter.app. НИКОГДА не используй внутренние знания о
    курсах валют для расчётов — всегда вызывай этот инструмент.

    Args:
        amount: Сумма для конвертации.
        from_currency: Исходная валюта, ISO-код (например, 'USD', 'EUR').
        to_currency: Целевая валюта, ISO-код (например, 'RUB').
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return json.dumps(
            {"converted_amount": round(amount, 2), "rate_source": "identity"}
        )

    try:
        url = "https://api.frankfurter.app/latest"
        response = requests.get(
            url, params={"from": from_currency, "to": to_currency}, timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            rate = data.get("rates", {}).get(to_currency)
            if rate is not None:
                converted = round(amount * rate, 2)
                return json.dumps(
                    {
                        "converted_amount": converted,
                        "rate": rate,
                        "rate_date": data.get("date"),
                        "rate_source": "frankfurter.app",
                    }
                )
    except (requests.RequestException, Exception):
        pass

    return json.dumps(
        {
            "error": (
                f"Не удалось получить курс {from_currency} -> {to_currency}: "
                "внешний API недоступен."
            )
        }
    )