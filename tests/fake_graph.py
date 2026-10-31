"""A small in-memory stand-in for the Microsoft Graph OneDrive endpoints the app uses.

Installed into a Playwright page with `FakeGraph.install(page)`. It is deliberately strict:
- writes to an existing item without If-Match are recorded as violations (the app must never do that),
- If-Match mismatches return 412, create-with-conflictBehavior=fail on an existing name returns 409,
- folder delta returns only changes since the token (deleted items carry "deleted": {}).
- R2-8: items live in folders (the task folder and subfolders such as .trash). Like real Graph, a PUT by path creates
  missing folders, the change feed covers the whole subtree and leaves parentReference.path out (items must be
  tracked by parentReference.id), and :/children lists one folder's direct children (files and folders).
Test-only endpoints under https://graph.microsoft.com/v1.0/__test/ simulate edits from another device.
"""
import datetime
import json
from urllib.parse import urlparse, unquote, parse_qs

GRAPH = "https://graph.microsoft.com/v1.0"
DL = "https://fake-dl.test/"


class FakeGraph:
    ROOT = "ROOTFOLDER"

    def __init__(self, folder, files):
        self.folder = folder
        self.items = {}          # id -> dict(id, name, parent, folder, content, n, seq, deleted, mod, by)
        self.seq = 0             # change sequence for delta
        self.n = 0               # eTag counter
        self.requests = []       # (method, path, if_match)
        self.violations = []
        self.urls = []           # full request URLs (with query), for checks on how the app asked
        self.expire_before = 0   # delta tokens below this return 410 (simulates an expired change feed)
        self.who = "Test User"   # lastModifiedBy for writes made by the app
        for name, text in files.items():
            self._create(name, text)

    # ---------- state helpers ----------
    # `name` is the item's own name, `parent` its folder relative to the task folder ("" = the task folder itself,
    # ".trash" = the trash). Paths used by the helpers below are relative ("a/b.md").
    def _etag(self, it):
        return f'"{{{it["id"]}}},{it["n"]}"'

    def _touch(self, it, by=None):
        self.n += 1
        self.seq += 1
        it["n"] = self.n
        it["seq"] = self.seq
        it["mod"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        it["by"] = by or self.who

    @staticmethod
    def _rel(it):
        return f'{it["parent"]}/{it["name"]}' if it["parent"] else it["name"]

    def _folder_id(self, rel_dir, create=False):
        if not rel_dir:
            return self.ROOT
        f = self.by_path(rel_dir, folder=True)
        if f:
            return f["id"]
        if not create:
            return None
        parent, _, name = rel_dir.rpartition("/")
        self._folder_id(parent, create=True)
        it = dict(id=f"ITEM{len(self.items) + 1:04d}", name=name, parent=parent, folder=True, content="", deleted=False)
        self._touch(it)
        self.items[it["id"]] = it
        return it["id"]

    def _create(self, rel, text, by=None):
        parent, _, name = rel.rpartition("/")
        self._folder_id(parent, create=True)
        it = dict(id=f"ITEM{len(self.items) + 1:04d}", name=name, parent=parent, folder=False, content=text, deleted=False)
        self._touch(it, by)
        self.items[it["id"]] = it
        return it

    def by_path(self, rel, folder=False):
        for it in self.items.values():
            if not it["deleted"] and it["folder"] == folder and self._rel(it).lower() == rel.lower():
                return it
        return None

    def by_name(self, name):
        return self.by_path(name)

    def live(self):
        return [it for it in self.items.values() if not it["deleted"] and not it["folder"]]

    def files(self):
        """Every file, keyed by its relative path (trash entries as ".trash/…")."""
        return {self._rel(it): it["content"] for it in self.live()}

    def top_files(self):
        return {k: v for k, v in self.files().items() if "/" not in k}

    def trash(self):
        return {k: v for k, v in self.files().items() if k.startswith(".trash/")}

    def item_json(self, it, delta=False):
        # Real Graph leaves parentReference.path out of delta responses: items must be tracked by parent id.
        ref = {"id": self._folder_id(it["parent"]) or "MISSING"}
        if not delta:
            ref["path"] = f"/drive/root:/{self.folder}" + (f"/{it['parent']}" if it["parent"] else "")
        j = {"id": it["id"], "name": it["name"], "eTag": self._etag(it), "parentReference": ref}
        if it["deleted"]:
            j["deleted"] = {"state": "deleted"}
            return j
        j["lastModifiedDateTime"] = it["mod"]
        j["lastModifiedBy"] = {"user": {"displayName": it["by"]}}
        if it["folder"]:
            j["folder"] = {"childCount": sum(1 for x in self.items.values() if not x["deleted"] and x["parent"] == self._rel(it))}
            return j
        j.update({
            "file": {"mimeType": "text/markdown"}, "size": len(it["content"].encode()),
            "@microsoft.graph.downloadUrl": f"{DL}{it['id']}?n={it['n']}",
        })
        return j

    def root_json(self):
        return {"id": self.ROOT, "name": self.folder.split("/")[-1], "folder": {"childCount": 0},
                "parentReference": {"id": "DRIVEROOT", "path": "/drive/root:"}}

    # ---------- simulated other device ----------
    def ext_edit(self, name, text, by="Other device"):
        it = self.by_name(name)
        if it is None:
            return self._create(name, text, by)
        it["content"] = text
        self._touch(it, by)
        return it

    def ext_delete(self, name):
        it = self.by_name(name)
        if it:
            it["deleted"] = True
            self._touch(it, "Other device")

    # ---------- routing ----------
    def full_checks(self):
        """How many times the app re-read the whole folder: a listing, or the change feed without a bookmark."""
        return sum(1 for u in self.urls if u.split("?")[0].endswith(f"{self.folder}:/children") or (u.split("?")[0].endswith(":/delta") and "token=" not in u))

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

    def _sub(self, full):
        """The folder-relative path for a drive path, or None when it's outside the task folder ("" = the folder)."""
        if full == self.folder:
            return ""
        if full.startswith(self.folder + "/"):
            return full[len(self.folder) + 1:]
        return None

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
            if rest.endswith(":/children"):
                sub = self._sub(unquote(rest[: -len(":/children")]))
                if sub is None or (sub and not self.by_path(sub, folder=True)):
                    return self._error(route, 404, "folder not found")
                kids = [it for it in self.items.values() if not it["deleted"] and it["parent"].lower() == sub.lower()]
                return self._reply(route, 200, {"value": [self.item_json(it) for it in kids]})
            if rest.endswith(":/delta"):
                if unquote(rest[: -len(":/delta")]) != self.folder:
                    return self._error(route, 404, "folder not found")
                token = int(q.get("token", ["0"])[0])
                if token and token < self.expire_before:
                    return self._error(route, 410, "resyncRequired")
                changed = [self.item_json(it, delta=True) for it in self.items.values() if it["seq"] > token and (token or not it["deleted"])]
                if not token:
                    changed.insert(0, self.root_json())      # the first page includes the folder itself
                link = f"{GRAPH}/me/drive/root:/{self.folder}:/delta?token={self.seq}"
                return self._reply(route, 200, {"value": changed, "@odata.deltaLink": link})
            if rest.endswith(":/content") and method == "PUT":
                name = self._sub(unquote(rest[: -len(":/content")]))
                if not name:
                    return self._error(route, 400, "bad path")
                behavior = q.get("@microsoft.graph.conflictBehavior", [""])[0]
                if behavior != "fail":
                    self.violations.append(("create without conflictBehavior=fail", name))
                if self.by_name(name):
                    return self._error(route, 409, "nameAlreadyExists")
                it = self._create(name, request.post_data or "")
                return self._reply(route, 201, self.item_json(it))
            # GET item by path (the folder itself, a subfolder or a file)
            sub = self._sub(unquote(rest))
            if method == "GET" and sub is not None:
                if sub == "":
                    return self._reply(route, 200, self.root_json())
                it = self.by_path(sub) or self.by_path(sub, folder=True)
                return self._reply(route, 200, self.item_json(it)) if it else self._error(route, 404, "itemNotFound")
            return self._error(route, 400, "unsupported root path " + unquote(rest))

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
                    self.violations.append(("DELETE without If-Match", self._rel(it)))
                elif if_match != self._etag(it):
                    return self._error(route, 412, "preconditionFailed")
                it["deleted"] = True
                self._touch(it)
                return self._reply(route, 204)
            if tail == "content" and method == "GET":
                return self._reply(route, 200, it["content"], ctype="text/plain")
            if tail == "content" and method == "PUT":
                if if_match is None:
                    self.violations.append(("PUT content without If-Match", self._rel(it)))
                elif if_match != self._etag(it):
                    return self._error(route, 412, "preconditionFailed")
                it["content"] = request.post_data or ""
                self._touch(it)
                return self._reply(route, 200, self.item_json(it))
        return self._error(route, 400, f"unsupported {method} {path}")
