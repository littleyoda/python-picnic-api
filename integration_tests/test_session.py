from python_picnic_api2.session import PicnicAPISession, PicnicAuthError
from python_picnic_api2.client import PicnicAPI
from requests import Session
from dotenv import load_dotenv
import os

load_dotenv()

username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
country_code = os.getenv("COUNTRY_CODE")

DEFAULT_URL = "https://storefront-prod.{}.picnicinternational.com/api/{}"
DEFAULT_API_VERSION = "15"


def test_init():
    assert issubclass(PicnicAPISession, Session)


def test_login():
    client = PicnicAPI(username=username, password=password,
                       country_code=country_code)
    assert "x-picnic-auth" in client.session.headers.keys()


def test_login_auth_error():
    try:
        PicnicAPI(username="doesnotexistblue@me.com", password="PasSWorD12345!",
                  country_code=country_code)
    except PicnicAuthError:
        assert True
    else:
        assert False
