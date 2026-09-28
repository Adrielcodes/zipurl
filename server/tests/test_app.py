import pytest

from app import create_app, is_valid_url


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    app.config["TESTING"] = True
    return app.test_client()


def shorten(client, url, alias=None):
    return client.post("/api/links", json={"url": url, "alias": alias})


@pytest.mark.parametrize(
    "url, ok",
    [
        ("https://github.com/Adrielcodes", True),
        ("http://example.com/path?q=1", True),
        ("javascript:alert(1)", False),
        ("ftp://example.com", False),
        ("github.com", False),
        ("https://localhost", False),
        ("", False),
    ],
)
def test_is_valid_url(url, ok):
    assert is_valid_url(url) is ok


def test_shorten_generates_code(client):
    res = shorten(client, "https://example.com")
    assert res.status_code == 201
    data = res.get_json()
    assert len(data["code"]) == 6
    assert data["url"] == "https://example.com"
    assert data["shortUrl"].endswith("/" + data["code"])
    assert data["clicks"] == 0


def test_custom_alias(client):
    res = shorten(client, "https://example.com", "my-link")
    assert res.status_code == 201
    assert res.get_json()["code"] == "my-link"


def test_duplicate_alias_rejected(client):
    shorten(client, "https://example.com", "taken")
    res = shorten(client, "https://other.com", "taken")
    assert res.status_code == 409


@pytest.mark.parametrize("alias", ["ab", "has space", "api", "x" * 33, "bad/slash"])
def test_invalid_alias_rejected(client, alias):
    assert shorten(client, "https://example.com", alias).status_code in (400, 409)


def test_invalid_url_rejected(client):
    res = shorten(client, "not a url")
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_redirect_counts_clicks(client):
    code = shorten(client, "https://example.com/page").get_json()["code"]

    for _ in range(3):
        res = client.get(f"/{code}")
        assert res.status_code == 302
        assert res.headers["Location"] == "https://example.com/page"

    stats = client.get(f"/api/links/{code}").get_json()
    assert stats["clicks"] == 3
    assert stats["lastClick"] is not None


def test_unknown_code_404(client):
    assert client.get("/nope123").status_code == 404
    assert client.get("/api/links/nope123").status_code == 404


def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}
