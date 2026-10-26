"""Exercise the committed redirect config in an isolated LOCAL nginx process.

Never run this exhaustive functional check against the production listener.
The process binds loopback on an ephemeral port, without upstreams or a DB.
"""
from __future__ import annotations

import argparse
import http.client
import json
import shlex
import shutil
import socket
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import quote


class LocalRedirectVerifier:
    def __init__(self, nginx: str, deploy: Path):
        self.nginx = nginx
        self.deploy = deploy
        self.elapsed_ms: list[float] = []
        self.checked = 0

    def assert_response(self, client, path, status, target=None, *, host="posletitrov.ru"):
        start = time.perf_counter()
        client.request("GET", quote(path, safe="/%?=&-._~"), headers={"Host": host})
        response = client.getresponse()
        body = response.read()
        elapsed = (time.perf_counter() - start) * 1000
        actual = (response.status, response.getheader("Location"))
        if actual != (status, target):
            raise AssertionError(f"{host}{path}: {actual!r} != {(status, target)!r}")
        self.checked += 1
        if status == 301:
            self.elapsed_ms.append(elapsed)
        return body

    def verify(self) -> dict:
        with tempfile.TemporaryDirectory(prefix="posletitrov-nginx-") as directory:
            root = Path(directory)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            source = (self.deploy / "posletitrov_server.conf").read_text()
            source = source.replace("listen 80;", f"listen 127.0.0.1:{port};")
            source = source.replace("listen [::]:80;", "")
            source = source.replace("/etc/nginx/posletitrov_redirects_generated.conf",
                                    str(self.deploy / "posletitrov_redirects_generated.conf"))
            source = source.replace("/var/www/static", directory + "/static")
            challenge = root / "static/.well-known/acme-challenge/check-token"
            challenge.parent.mkdir(parents=True)
            challenge.write_text("public-validation-token")
            config = root / "nginx.conf"
            config.write_text(f"worker_processes 1;\npid {root}/nginx.pid;\n"
                              f"error_log {root}/error.log;\nevents {{ worker_connections 128; }}\n"
                              "http { access_log off; map_hash_bucket_size 256; map_hash_max_size 524288;\n"
                              + source + "\n}\n")
            command = [self.nginx, "-p", directory + "/", "-c", str(config)]
            subprocess.run(command + ["-t"], check=True, capture_output=True)
            subprocess.run(command, check=True, capture_output=True)
            try:
                client = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                for line in (self.deploy / "posletitrov_redirects_generated.conf").read_text().splitlines():
                    if not line.lstrip().startswith('"/'):
                        continue
                    path, target = shlex.split(line.strip().removesuffix(";"))
                    self.assert_response(client, path, 301, target,
                                         host="www.posletitrov.ru" if self.checked % 2 else "posletitrov.ru")
                    if self.checked % 100 == 0 or not path.isascii():
                        self.assert_response(client, path.upper() + "?utm_source=test", 301, target)
                community = "https://tambur.pub/comuns/after_the_credits"
                archives = {"": "", "/articles": "", "/podborki": "", "/articles/tv-series": "?category=serialy",
                            "/articles/movies": "?category=filmy", "/articles/movies/movie-tops": "?category=filmy",
                            "/articles/movies/reviews": "?category=filmy"}
                for prefix, query in archives.items():
                    for suffix in ("/page/2", "/PAGE/999999/?utm_source=old"):
                        self.assert_response(client, prefix + suffix, 301, community + query)
                for path in ("/missing-old-page", "/wp-admin/", "/xmlrpc.php", "/articles/page/nope/",
                             "/articles/page/2/not-a-page", "/fake/articles/page/2"):
                    self.assert_response(client, path, 410)
                self.assert_response(client, "/robots.txt", 200)
                self.assert_response(client, "/sitemap.xml", 301, "https://tambur.pub/sitemap.xml")
                body = self.assert_response(client, "/.well-known/acme-challenge/check-token", 200)
                assert body == b"public-validation-token"
                self.assert_response(client, "/.well-known/acme-challenge/missing", 404)
                for name in ("test.jpg", "Screenshot2024-12-17at8.14.04%E2%80%AFAM-1024x569.jpg"):
                    self.assert_response(client, "/wp-content/uploads/2025/03/" + name + "?x=1", 301,
                                         "https://media.tambur.pub/legacy-wp/uploads/2025/03/" + name)
                client.close()
            finally:
                subprocess.run(command + ["-s", "quit"], check=True, capture_output=True)
            return {"checked_responses": self.checked, "redirect_responses": len(self.elapsed_ms),
                    "local_median_ms": round(statistics.median(self.elapsed_ms), 3),
                    "local_p95_ms": round(sorted(self.elapsed_ms)[int(len(self.elapsed_ms) * .95)], 3),
                    "local_max_ms": round(max(self.elapsed_ms), 3),
                    "environment": "isolated local nginx, one sequential client, no upstream or SQL",
                    "production_load_test": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nginx", default=shutil.which("nginx"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.nginx:
        parser.error("Install local nginx or pass --nginx /path/to/nginx")
    report = LocalRedirectVerifier(args.nginx, Path(__file__).resolve().parent).verify()
    output = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
