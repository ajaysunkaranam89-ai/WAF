# Web Application Firewalls on Kubernetes (kind)

Two open-source WAFs for the notes app and python app. Both run side by side; keep the one you prefer.

| | **BunkerWeb** (has a web GUI) | **ModSecurity + OWASP CRS** (no GUI) |
|---|---|---|
| Folder | [`bunkerweb/`](bunkerweb) | [`k8s/`](k8s) |
| Namespace | `bunkerweb` | `waf` |
| How apps are protected | Kubernetes **Ingress** (class `bunkerweb`) | one reverse-proxy pod per app (ports 8081/8082) |
| Pods / memory | 6 pods (~1 GB) | 2 pods (~150 MB) |
| GUI | yes: setup wizard, sites, blocked requests | none (pod logs only) |

---

# A. BunkerWeb (GUI)

[BunkerWeb](https://github.com/bunkerity/bunkerweb) = nginx + ModSecurity + OWASP Core Rule Set + bad-behavior bans, with a web UI.
Installed from the official Helm chart (`bunkerweb/bunkerweb` 1.3.0, BunkerWeb 1.6.17). **No secrets are stored in this repo.**

Components (namespace `bunkerweb`): `mybw-bunkerweb` (the WAF), `scheduler`, `controller` (watches Ingresses), `ui`, `mariadb`, `redis`.

## Install
```bash
helm repo add bunkerweb https://repo.bunkerweb.io/charts
helm repo update
helm install mybw bunkerweb/bunkerweb -n bunkerweb --create-namespace -f bunkerweb/values.yaml
kubectl apply -f bunkerweb/ingresses.yaml        # protects the two apps
kubectl get pods -n bunkerweb                    # all 1/1 Running (first start pulls images)
```
Uninstall: `kubectl delete -f bunkerweb/ingresses.yaml && helm uninstall mybw -n bunkerweb && kubectl delete namespace bunkerweb`

## Open the GUI
```bash
kubectl port-forward -n bunkerweb svc/ui-mybw-bunkerweb 7000:7000
```
Open **http://localhost:7000** (redirects to the setup wizard). The wizard asks you to create the admin username and password
yourself: choose your own and do not commit it. Later logins use the same page.

## Use the protected apps
The Ingresses use lab hostnames `notes.waf.local` and `python.waf.local`:
```bash
kubectl port-forward -n bunkerweb svc/mybw-bunkerweb-external 8080:80
```
- With curl: `curl -H "Host: notes.waf.local" http://localhost:8080/`
- In a browser: add `127.0.0.1 notes.waf.local python.waf.local` to `C:\Windows\System32\drivers\etc\hosts`, then open http://notes.waf.local:8080

## Verified (2026-11-03, kind)
| Request (Host: notes.waf.local and python.waf.local) | Result |
|---|---|
| `GET /` | 200, passes through |
| `/?id=1' OR '1'='1` (SQL injection) | **403 blocked** |
| `/?q=<script>alert(1)</script>` (XSS) | **403 blocked** |
| GUI service | 303 to `/setup` (wizard) |

Note: after a few blocked requests from one address BunkerWeb's *bad behavior* feature briefly bans it (HTTP 429), then it recovers.

## Maintenance mode (python app, through BunkerWeb)
`bunkerweb/maintenance-python.yaml` is a ConfigMap that BunkerWeb loads as a custom nginx config for `python.waf.local`:
every request gets **HTTP 503** and a "We will be back soon" page (with `Retry-After`); the app itself is untouched and
other sites (notes) keep working. Only traffic that goes **through BunkerWeb** is affected, not direct forwards to the app.
```bash
kubectl apply  -f bunkerweb/maintenance-python.yaml     # maintenance ON  (takes effect in ~30 s)
kubectl delete -f bunkerweb/maintenance-python.yaml     # maintenance OFF
```
To do the same for another site, copy the file and change `namespace` and the `bunkerweb.io/CONFIG_SITE` hostname.
Tip: test with `127.0.0.1`, not `localhost`: on Windows `localhost` tries IPv6 first, where Docker Desktop answers on port 8080.

## Settings (`bunkerweb/values.yaml`)
`securityMode: block` (use `detect` to only log), ModSecurity + CRS v4 on, `service.type: ClusterIP` (kind has no LoadBalancer).
Per-site settings go in Ingress annotations (`bunkerweb.io/<SETTING>`); to protect another app add an Ingress with `ingressClassName: bunkerweb` in the app's namespace.

---

# B. ModSecurity + OWASP CRS (no GUI)

## What gets deployed (namespace `waf`)

| Deployment / Service | Listens on | Forwards to |
|---|---|---|
| `waf-notes` | `8081` | `http://notes-app.notes.svc.cluster.local:80` |
| `waf-python` | `8082` | `http://python-app-service.python-app.svc.cluster.local:80` |

Image: `owasp/modsecurity-crs:nginx-alpine`. Each pod uses about 64 Mi requested (256 Mi limit).

## Install / uninstall

```bash
kubectl apply -f k8s/waf.yaml
kubectl get pods -n waf                       # both 1/1 Running
kubectl delete namespace waf                  # uninstall (apps are untouched)
```

## Use it

Clients must talk to the WAF instead of the app. Localhost-only forwards:

```bash
kubectl port-forward -n waf svc/waf-notes 8081:8081
kubectl port-forward -n waf svc/waf-python 8082:8082
```
To reach them from other machines, add `--address 0.0.0.0` (and open the Windows firewall port).

## Verified (2026-11-03, kind, both apps)

| Request | Result |
|---|---|
| `GET /` | 200, passes through to the app |
| `GET /?id=1' OR '1'='1` (SQL injection) | **403 blocked** |
| `GET /?q=<script>alert(1)</script>` (XSS) | **403 blocked** |
| `GET /../../etc/passwd` (path traversal) | **400 rejected** |
| scanner user-agent `sqlmap/1.7` | **403 blocked** |
| notes app `/health` through the WAF | `{"status":"ok","db":"up"}` |

Re-run the checks:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8081/
curl -s -o /dev/null -w "%{http_code}\n" -G http://localhost:8081/ --data-urlencode "id=1' OR '1'='1"
curl -s -o /dev/null -w "%{http_code}\n" -G http://localhost:8081/ --data-urlencode "q=<script>alert(1)</script>"
```

## Tuning (environment variables in `k8s/waf.yaml`)

| Variable | Meaning |
|---|---|
| `MODSEC_RULE_ENGINE` | `On` = block attacks; `DetectionOnly` = only log (use this first on a new app to find false positives) |
| `BLOCKING_PARANOIA` | CRS paranoia level 1-4. 1 = fewest false positives, 4 = strictest |
| `BACKEND` | upstream URL the WAF forwards to |
| `PORT` | port the WAF listens on |

Blocked requests are logged by the pod: `kubectl logs -n waf deploy/waf-notes`.

## Add another protected app
Copy one Deployment + Service pair in `k8s/waf.yaml`, change the names, `PORT` and `BACKEND`.

## Limits
This is a lab setup: no TLS termination (terminate TLS in front of the WAF), no rate limiting, a single replica per app,
and CRS only (no custom rules). A WAF reduces risk but does not replace fixing the application.
