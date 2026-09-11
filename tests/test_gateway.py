from local_dev_agent.gateway.bailian import BailianProvider
from local_dev_agent.gateway.openai_compat import auth_headers
from local_dev_agent.gateway.zhongtai import ZhongtaiProvider


def test_zhongtai_uses_x_api_key_header() -> None:
    headers = auth_headers("ak_test", "x-api-key")
    assert headers["X-API-Key"] == "ak_test"
    assert "Authorization" not in headers


def test_bailian_uses_bearer_header() -> None:
    headers = auth_headers("sk-test", "bearer")
    assert headers["Authorization"] == "Bearer sk-test"
    assert "X-API-Key" not in headers


def test_provider_clients_set_expected_auth() -> None:
    with ZhongtaiProvider(api_key="ak_test") as zhongtai:
        assert zhongtai._client.headers["X-API-Key"] == "ak_test"
        assert zhongtai.auth == "x-api-key"
    with BailianProvider(api_key="sk-test") as bailian:
        assert bailian._client.headers["Authorization"] == "Bearer sk-test"
        assert bailian.auth == "bearer"
