"""A small in-memory stand-in for the Microsoft Graph OneDrive endpoints the app uses.

Installed into a Playwright page with `FakeGraph.install(page)`. It is deliberately strict:
- writes to an existing item without If-Match are recorded as violations (the app must never do that),
- If-Match mismatches return 412, create-with-conflictBehavior=fail on an existing name returns 409,
- folder delta returns only changes since the token (deleted items carry "deleted": {}).
Test-only endpoints under https://graph.microsoft.com/v1.0/__test/ simulate edits from another device.
"""
import json
from urllib.parse import urlparse, unquote, parse_qs

GRAPH = "https://graph.microsoft.com/v1.0"
DL = "https://fake-dl.test/"


class FakeGraph:
    def __init__(self, folder, files):
        self.folder = folder
        self.items = {}          # id -> dict(id, name, content, n, seq, deleted)
        self.seq = 0             # change sequence for delta
        self.n = 0               # eTag counter
        self.requests = []       # (method, path, if_match)
        self.violations = []
        self.urls = []           # full request URLs (with query), for checks on how the app asked
        self.expire_before = 0   # delta tokens below this return 410 (simulates an expired change feed)
        for name, text in files.items():
            self._create(name, text)

    # ---------- state helpers ----------
    def _etag(self, it):
        return f'"{{{it["id"]}}},{it["n"]}"'

    def _touch(self, it):
        self.n += 1
        self.seq += 1
        it["n"] = self.n
        it["seq"] = self.seq

    def _create(self, name, text):
        it = dict(id=f"ITEM{len(self.items) + 1:04d}", name=name, content=text, deleted=False)
        self._touch(it)
        self.items[it["id"]] = it
        return it

    def by_name(self, name):
        for it in self.items.values():
            if not it["deleted"] and it["name"].lower() == name.lower():
                return it
        return None

    def live(self):
        return [it for it in self.items.values() if not it["deleted"]]

    def files(self):
        return {it["name"]: it["content"] for it in self.live()}

    def item_json(self, it):
        j = {
            "id": it["id"], "name": it["name"], "eTag": self._etag(it),
            "parentReference": {"path": f"/drive/root:/{self.folder}"},
        }
        if it["deleted"]:
            j["deleted"] = {"state": "deleted"}
            return j
        j.update({
            "file": {"mimeType": "text/markdown"}, "size": len(it["content"].encode()),
            "lastModifiedDateTime": "2026-10-17T00:00:00Z",
            "@microsoft.graph.downloadUrl": f"{DL}{it['id']}?n={it['n']}",
        })
        return j

    # ---------- simulated other device ----------
    def ext_edit(self, name, text):
        it = self.by_name(name)
        if it is None:
            return self._create(name, text)
        it["content"] = text
        self._touch(it)
        return it

    def ext_delete(self, name):
        it = self.by_name(name)
        if it:
            it["deleted"] = True
            self._touch(it)

    # ---------- routing ----------
    def full_checks(self):
        """How many times the app re-read the whole folder: a listing, or the change feed without a bookmark."""
        return sum(1 for u in self.urls if u.split("?")[0].endswith(":/children") or (u.split("?")[0].endswith(":/delta") and "token=" not in u))

    def downloads(self):
        return sum(1 for u in self.urls if u.startswith(DL))

    def install(self, page):
        page.route("https://graph.microsoft.com/**", self._handle)
        page.route("https://fake-dl.test/**", self._download)

    def _reply(self, route, status, body=None, ctype="application/json"):
        if body is None:
            route.fulfill(status=status, body="", headers={"Access-Control-Allow-Origin": "*"})
        elif isinstance(body, str) and ctype != "application/json":
            route.fulfill(status=status, body=body, headers={"Content-Type": ctype, "Access-Control-Allow-Origin": "*"})
        else:
            route.fulfill(status=status, body=json.dumps(body), headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"})

    def _error(self, route, status, msg):
        self._reply(route, status, {"error": {"code": str(status), "message": msg}})

    def _download(self, route, request):
        self.urls.append(request.url)
        iid = urlparse(request.url).path.strip("/")
        it = self.items.get(iid)
        if not it or it["deleted"]:
            return route.fulfill(status=404, body="gone", headers={"Access-Control-Allow-Origin": "*"})
        route.fulfill(status=200, body=it["content"], headers={"Content-Type": "text/plain", "Access-Control-Allow-Origin": "*"})

    def _handle(self, route, request):
        if request.method == "OPTIONS":
            return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*",
                                                      "Access-Control-Allow-Methods": "GET,PUT,DELETE,POST"})
        u = urlparse(request.url)
        path = u.path[len("/v1.0"):] if u.path.startswith("/v1.0") else u.path
        q = parse_qs(u.query)
        method = request.method
        if_match = request.headers.get("if-match")
        self.requests.append((method, unquote(path), if_match))
        self.urls.append(unquote(request.url))

        # test-only endpoints
        if path.startswith("/__test/"):
            body = json.loads(request.post_data or "{}")
            if path == "/__test/edit":
                self.ext_edit(body["name"], body["text"])
            elif path == "/__test/delete":
                self.ext_delete(body["name"])
            return self._reply(route, 200, {"ok": True, "files": self.files()})

        if path == "/me":
            return self._reply(route, 200, {"userPrincipalName": "test@example.com"})

        root = "/me/drive/root:/"
        if path.startswith(root):
            rest = path[len(root):]
            folder_enc_len = len(rest.split(":")[0]) if rest.endswith((":/children", ":/delta")) else None
            if rest.endswith(":/children"):
                if unquote(rest[: -len(":/children")]) != self.folder:
                    return self._error(route, 404, "folder not found")
                return self._reply(route, 200, {"value": [self.item_json(it) for it in self.live()]})
            if rest.endswith(":/delta"):
                if unquote(rest[: -len(":/delta")]) != self.folder:
                    return self._error(route, 404, "folder not found")
                token = int(q.get("token", ["0"])[0])
                if token and token < self.expire_before:
                    return self._error(route, 410, "resyncRequired")
                changed = [self.item_json(it) for it in self.items.values() if it["seq"] > token and (token or not it["deleted"])]
                link = f"{GRAPH}/me/drive/root:/{self.folder}:/delta?token={self.seq}"
                return self._reply(route, 200, {"value": changed, "@odata.deltaLink": link})
            if rest.endswith(":/content") and method == "PUT":
                full = unquote(rest[: -len(":/content")])
                if not full.startswith(self.folder + "/"):
                    return self._error(route, 400, "bad path")
                name = full[len(self.folder) + 1:]
                behavior = q.get("@microsoft.graph.conflictBehavior", [""])[0]
                if behavior != "fail":
                    self.violations.append(("create without conflictBehavior=fail", name))
                if self.by_name(name):
                    return self._error(route, 409, "nameAlreadyExists")
                it = self._create(name, request.post_data or "")
                return self._reply(route, 201, self.item_json(it))
            # GET item by path
            full = unquote(rest)
            if method == "GET" and full.startswith(self.folder + "/"):
                it = self.by_name(full[len(self.folder) + 1:])
                return self._reply(route, 200, self.item_json(it)) if it else self._error(route, 404, "itemNotFound")
            return self._error(route, 400, "unsupported root path " + full)

        if path.startswith("/me/drive/items/"):
            rest = path[len("/me/drive/items/"):]
            iid, _, tail = rest.partition("/")
            it = self.items.get(iid)
            if not it or it["deleted"]:
                return self._error(route, 404, "itemNotFound")
            if tail == "" and method == "GET":
                return self._reply(route, 200, self.item_json(it))
            if tail == "" and method == "DELETE":
                if if_match is None:
                    self.violations.append(("DELETE without If-Match", it["name"]))
                elif if_match != self._etag(it):
                    return self._error(route, 412, "preconditionFailed")
                it["deleted"] = True
                self._touch(it)
                return self._reply(route, 204)
            if tail == "content" and method == "GET":
                return self._reply(route, 200, it["content"], ctype="text/plain")
            if tail == "content" and method == "PUT":
                if if_match is None:
                    self.violations.append(("PUT content without If-Match", it["name"]))
                elif if_match != self._etag(it):
                    return self._error(route, 412, "preconditionFailed")
                it["content"] = request.post_data or ""
                self._touch(it)
                return self._reply(route, 200, self.item_json(it))
        return self._error(route, 400, f"unsupported {method} {path}")
