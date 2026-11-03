# Web Application Firewall on Kubernetes (kind): ModSecurity + OWASP CRS

Kubernetes manifests for an open-source WAF in front of two apps. It uses the
[OWASP ModSecurity Core Rule Set](https://github.com/coreruleset/modsecurity-crs-docker) image (nginx + ModSecurity v3 +
the OWASP Core Rule Set). Each protected app gets one small reverse-proxy Deployment: clean requests are forwarded to the
app's Service, attacks get an HTTP 403. No secrets, no database, no volumes.

> History: SafeLine (Chaitin) was tried first and removed. Its stack needs a detector management token that the
> Docker Compose file does not document, so adding a site always failed with `rules compile error`
> (detector answered `401 without valid token` to fvm/luigi). ModSecurity + CRS is simpler and has no such dependency.

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
