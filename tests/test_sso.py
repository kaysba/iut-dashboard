"""Tests de la connexion CAS commune (sources/sso.py), avec un faux CAS."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sources.common import SourceError  # noqa: E402
from sources.sso import cas_login  # noqa: E402

LOGIN_PAGE = b'<form action="/login" method="post"><input name="username" type="text">' \
             b'<input name="password" type="password"><input name="execution" type="hidden" value="e1s1"></form>'
RELAY = b'<form action="https://site.test/back" method="post"><input name="SAMLResponse" type="hidden" value="abc"></form>'


class FakeCAS:
    def __init__(self, accept=True, cookie=False):
        self.accept, self.cookie, self.posts, self.jar = accept, cookie, [], []

    def request(self, url, data=None, **kw):
        if url.startswith("https://site.test/start"):
            return (200, "https://cas.test/login?service=x", {}, RELAY if self.cookie else LOGIN_PAGE)
        if url == "https://cas.test/login":
            self.posts.append(data)
            return (200, "https://cas.test/login", {}, RELAY if self.accept else LOGIN_PAGE)
        if url == "https://site.test/back":
            self.posts.append(data)
            return 200, "https://site.test/home", {}, b"<html>ok</html>"
        raise AssertionError(url)


done = lambda u: u.startswith("https://site.test/home")  # noqa: E731


class CasTest(unittest.TestCase):
    def test_mot_de_passe_puis_relais(self):
        s = FakeCAS()
        url, _ = cas_login(s, "https://site.test/start", "etu", "pw", done)
        self.assertEqual(url, "https://site.test/home")
        self.assertEqual(s.posts[0], {"username": "etu", "password": "pw", "execution": "e1s1"})

    def test_cookie_du_cas_pas_de_mot_de_passe(self):
        s = FakeCAS(cookie=True)
        cas_login(s, "https://site.test/start", "etu", "pw", done)
        self.assertEqual([p for p in s.posts if p and "password" in p], [])

    def test_mot_de_passe_refuse(self):
        with self.assertRaises(SourceError) as cm:
            cas_login(FakeCAS(accept=False), "https://site.test/start", "etu", "mauvais", done, refused="Refusé !")
        self.assertEqual(str(cm.exception), "Refusé !")


if __name__ == "__main__":
    unittest.main()
