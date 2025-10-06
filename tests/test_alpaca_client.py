import pytest
import requests_mock
from smartcfd.alpaca_client import get_alpaca_client, OrderRequest, OrderResponse

API_BASE = "https://paper-api.alpaca.markets"

@pytest.fixture
def client():
    """Fixture to create an AlpacaClient with a mock session."""
    return get_alpaca_client(API_BASE)

def test_post_market_order_success(client, requests_mock):
    """
    Verify that a simple market order can be successfully posted and parsed.
    """
    # Mock the API response
    mock_response_payload = {
        "id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
        "client_order_id": "my-unique-client-order-id",
        "created_at": "2025-10-06T10:30:00Z",
        "updated_at": "2025-10-06T10:30:00Z",
        "submitted_at": "2025-10-06T10:30:00Z",
        "filled_at": None,
        "expired_at": None,
        "canceled_at": None,
        "failed_at": None,
        "replaced_at": None,
        "replaced_by": None,
        "replaces": None,
        "asset_id": "b0b6dd9d-8b9b-48a9-ba46-b9d54906e415",
        "symbol": "AAPL",
        "asset_class": "us_equity",
        "notional": None,
        "qty": "1",
        "filled_qty": "0",
        "filled_avg_price": None,
        "order_class": "simple",
        "type": "market",
        "side": "buy",
        "time_in_force": "day",
        "limit_price": None,
        "stop_price": None,
        "status": "accepted",
        "extended_hours": False,
        "legs": None,
        "trail_price": None,
        "trail_percent": None,
        "hwm": None,
    }
    requests_mock.post(f"{API_BASE}/v2/orders", json=mock_response_payload, status_code=200)

    # Create the order request
    order_request = OrderRequest(
        symbol="AAPL",
        qty="1",
        side="buy",
        type="market",
        time_in_force="day",
        client_order_id="my-unique-client-order-id",
    )

    # Post the order
    order_response = client.post_order(order_request)

    # Assertions
    assert isinstance(order_response, OrderResponse)
    assert order_response.id == "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"
    assert order_response.symbol == "AAPL"
    assert order_response.status == "accepted"
    assert order_response.order_type == "market"

def test_retry_logic_on_5xx_error(client, requests_mock):
    """
    Verify that the client retries on a 503 Service Unavailable error.
    """
    # Mock a sequence of responses: 503, then 200
    mock_responses = [
        {"status_code": 503},
        {"status_code": 200, "json": {
            "id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6", "client_order_id": "retry-test",
            "created_at": "2025-10-06T10:30:00Z", "updated_at": "2025-10-06T10:30:00Z",
            "submitted_at": "2025-10-06T10:30:00Z", "asset_id": "b0b6dd9d-8b9b-48a9-ba46-b9d54906e415",
            "symbol": "GOOG", "asset_class": "us_equity", "qty": "1", "filled_qty": "0",
            "order_class": "simple", "type": "market", "side": "buy", "time_in_force": "day",
            "status": "accepted", "extended_hours": False
        }},
    ]
    requests_mock.post(f"{API_BASE}/v2/orders", mock_responses)

    order_request = OrderRequest(
        symbol="GOOG",
        qty="1",
        side="buy",
        type="market",
        time_in_force="day",
        client_order_id="retry-test",
    )

    # This should succeed after one retry
    order_response = client.post_order(order_request)

    assert requests_mock.call_count == 2
    assert order_response.status == "accepted"
    assert order_response.symbol == "GOOG"
