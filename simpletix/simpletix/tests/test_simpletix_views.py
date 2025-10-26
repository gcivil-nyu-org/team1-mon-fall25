import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_index_view(client):
    """
    Test the index view returns 200 OK, uses the correct template,
    and passes the correct keyword context.
    """
    url = reverse("simpletix:index")
    response = client.get(url)

    assert response.status_code == 200
    assert response.templates[0].name == "simpletix/index.html"

    # Check the context dictionary passed to the template
    assert "keyword" in response.context
    assert len(response.templates) > 0
    assert response.context["keyword"] == "Homepage"


@pytest.mark.parametrize("test_keyword", ["AboutUs", "ContactPage"])
def test_webpage_view_with_keyword(client, test_keyword):
    """
    Test the webpage view returns 200 OK, uses the correct template,
    and passes the provided keyword context.
    """
    url = reverse("simpletix:webpage", args=[test_keyword])
    response = client.get(url)

    assert response.status_code == 200
    assert len(response.templates) > 0
    assert response.templates[0].name == "simpletix/index.html"

    # Check the context dictionary passed to the template
    assert "keyword" in response.context
    assert response.context["keyword"] == test_keyword
