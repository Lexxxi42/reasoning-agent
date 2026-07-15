import json
from unittest.mock import MagicMock, patch

import pytest

from tools import convert_currency, get_obligations

def test_get_obligations_returns_all_by_default():
    result = get_obligations.invoke({})
    assert isinstance(result, list)
    assert len(result) == 15

def test_get_obligations_filters_by_category():
    result = get_obligations.invoke({"category": "subscription"})
    assert len(result) == 4
    assert all(item["category"] == "subscription" for item in result)

def test_get_obligations_filters_by_status():
    result = get_obligations.invoke({"status": "cancelled"})
    assert len(result) == 1
    assert result[0]["title"] == "HBO Max"

def test_get_obligations_filters_by_date_range():
    result = get_obligations.invoke(
        {"start_date": "2026-06-01", "end_date": "2026-07-10"}
    )
    titles = {item["title"] for item in result}
    assert "Yandex Plus" not in titles
    assert "Netflix" in titles
    assert "Apple Music" in titles

def test_get_obligations_combined_filters():
    result = get_obligations.invoke(
        {"category": "subscription", "status": "active", "end_date": "2026-07-02"}
    )
    titles = {item["title"] for item in result}
    assert titles == {"Netflix", "Spotify Premium", "Apple Music"}

# convert_currency

def test_convert_currency_same_currency_no_api_call():
    result = json.loads(convert_currency.invoke(
        {"amount": 100, "from_currency": "USD", "to_currency": "USD"}
    ))
    assert result["converted_amount"] == 100
    assert result["rate_source"] == "identity"

@patch("tools.requests.get")
def test_convert_currency_success_via_api(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "rate": 90.0,
        "date": "2026-07-14",
    }
    mock_get.return_value = mock_response

    result = json.loads(convert_currency.invoke(
        {"amount": 10, "from_currency": "usd", "to_currency": "rub"}
    ))
    assert result["converted_amount"] == 900.0
    assert result["rate_source"] == "frankfurter.dev"

@patch("tools.requests.get")
def test_convert_currency_falls_back_when_api_down(mock_get):
    mock_get.side_effect = Exception("network error")

    result = json.loads(convert_currency.invoke(
        {"amount": 10, "from_currency": "USD", "to_currency": "RUB"}
    ))
    assert "error" in result

@patch("tools.requests.get")
def test_convert_currency_reports_error_when_no_fallback(mock_get):
    mock_get.side_effect = Exception("network error")

    result = json.loads(convert_currency.invoke(
        {"amount": 10, "from_currency": "GBP", "to_currency": "JPY"}
    ))
    assert "error" in result

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
