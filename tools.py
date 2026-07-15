import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

import requests
from langchain_core.tools import tool

DATA_PATH = Path(__file__).parent / "data" / "obligations.json"

def _load_obligations() -> list[dict]:
    """Читает и парсит JSON-фикстуру с диска."""
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
def resolve_date_range(period: str) -> str:
    """
    Детерминированно вычисляет диапазон дат [start_date, end_date] для типового
    периода, отсчитываемого от СЕГОДНЯШНЕЙ даты. Используй этот инструмент ВСЕГДА,
    когда нужен диапазон дат по фразам вроде "эта неделя", "ближайшие 30 дней",
    "этот месяц" — НЕ вычисляй даты самостоятельно в уме, это ненадёжно.

    Args:
        period: Один из: 'this_week' (текущая календарная неделя, пн-вс),
                'next_7_days', 'next_30_days', 'this_month' (текущий календарный
                месяц), 'next_month'.

    Returns:
        JSON с полями start_date, end_date (формат YYYY-MM-DD) и today.
    """
    today = datetime.now()
    period = period.strip().lower()

    if period == "this_week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif period == "next_7_days":
        start = today
        end = today + timedelta(days=7)
    elif period == "next_30_days":
        start = today
        end = today + timedelta(days=30)
    elif period == "this_month":
        start = today.replace(day=1)
        if today.month == 12:
            next_month_start = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month_start = today.replace(month=today.month + 1, day=1)
        end = next_month_start - timedelta(days=1)
    elif period == "next_month":
        if today.month == 12:
            start = today.replace(year=today.year + 1, month=1, day=1)
        else:
            start = today.replace(month=today.month + 1, day=1)
        if start.month == 12:
            next_month_start = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_month_start = start.replace(month=start.month + 1, day=1)
        end = next_month_start - timedelta(days=1)
    else:
        return json.dumps(
            {
                "error": (
                    f"Неизвестный период '{period}'. Допустимые значения: "
                    "this_week, next_7_days, next_30_days, this_month, next_month."
                )
            }
        )

    return json.dumps(
        {
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "today": today.strftime("%Y-%m-%d"),
        }
    )


@tool
def get_obligations(
    status: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list | str:
    """
    Возвращает список финансовых обязательств пользователя (подписки, платежи,
    коммунальные услуги и т.д.) из локальной базы.

    Args:
        status: Фильтр по статусу ('active', 'canceled'). Если не указан — все статусы.
        category: Фильтр по категории ('subscription', 'software', 'storage', 'streaming').
                  Если не указан — все категории.
        start_date: Начало диапазона по дате следующего списания, формат YYYY-MM-DD.
                    Используй, когда нужно посчитать траты "в ближайшие N дней" или
                    "на этой неделе" — start_date обычно равен сегодняшней дате.
        end_date: Конец диапазона по дате следующего списания, формат YYYY-MM-DD.

    Returns:
        Список обязательств (словарей с полями id, title, amount, currency,
        category, next_payment_date, status), либо строка с описанием ошибки.
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

    return result


@tool
def calculate_total_spending(
    target_currency: str = "RUB",
    category: Optional[str] = None,
    status: Optional[str] = "active",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """
    Вычисляет общую сумму расходов по подпискам, конвертируя все в целевую валюту.
    Это ГЛАВНЫЙ инструмент для ответа на вопросы «сколько всего потрачено» —
    используй его вместо вызова get_obligations + множественных convert_currency.

    Args:
        target_currency: Валюта для итога (по умолчанию RUB).
        category: Фильтр по категории (опционально).
        status: Фильтр по статусу (по умолчанию 'active', только активные платежи).
        start_date: Начало диапазона по next_payment_date (YYYY-MM-DD). Если нужен
                    диапазон для периода вроде "эта неделя"/"30 дней", СНАЧАЛА вызови
                    resolve_date_range и подставь его start_date сюда.
        end_date: Конец диапазона по next_payment_date (YYYY-MM-DD).

    Returns:
        JSON с полями: total_amount, target_currency, items_count, currency_breakdown,
        warnings (если были ошибки конвертации).
    """
    obligations = get_obligations.invoke(
        {
            "category": category,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
        }
    )
    if isinstance(obligations, str):  # ошибка
        return json.dumps({"error": obligations})

    total = 0.0
    currency_breakdown = {}
    conversion_errors = []
    fallback_used = False

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
            if "warning" in result:
                fallback_used = True
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
            "fallback_rates_used": fallback_used,
        }
    )

@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Конвертирует сумму из одной валюты в другую.
    Для RUB использует новый Frankfurter API, для остальных валют — старый API.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return json.dumps({
            "converted_amount": round(amount, 2),
            "rate_source": "identity"
        })

    if from_currency == "RUB" or to_currency == "RUB":
        try:
            url = f"https://api.frankfurter.dev/v2/rate/{from_currency}/{to_currency}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                rate = data.get("rate")
                if rate is not None:
                    return json.dumps({
                        "converted_amount": round(amount * rate, 2),
                        "rate": rate,
                        "rate_date": data.get("date"),
                        "rate_source": "frankfurter.dev",
                    })
        except Exception:
            pass
    else:
        try:
            url = "https://api.frankfurter.app/latest"
            response = requests.get(
                url,
                params={"from": from_currency, "to": to_currency},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                rate = data.get("rates", {}).get(to_currency)
                if rate is not None:
                    return json.dumps({
                        "converted_amount": round(amount * rate, 2),
                        "rate": rate,
                        "rate_date": data.get("date"),
                        "rate_source": "frankfurter.app",
                    })
        except Exception:
            pass
    return json.dumps({
        "error": f"Не удалось получить курс {from_currency} -> {to_currency}"
    })