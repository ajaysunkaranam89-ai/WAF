# SafeLine WAF on Kubernetes (kind)

Kubernetes manifests to run [Chaitin SafeLine](https://github.com/chaitin/SafeLine) (open-source web application firewall,
Community Edition 9.4.3) on a small kind cluster. SafeLine officially ships only as Docker Compose, so this is a port of its
`compose.yaml`. **No secrets are stored in this repo.**

## What gets deployed (namespace `safeline`)

| Component | Image | Role |
|---|---|---|
| `safeline-pg` | `chaitin/safeline-postgres:15.2` | PostgreSQL (2 Gi volume) |
| `safeline-mgt` | `chaitin/safeline-mgt-g:9.4.3` | management console (HTTPS on port 1443) |
| `safeline-detector` | `chaitin/safeline-detector-g:9.4.3` | attack-detection engine |
| `safeline-tengine` | `chaitin/safeline-tengine-g:9.4.3` | the WAF / reverse proxy (ports 80, 443) |
| `safeline-luigi`, `safeline-fvm`, `safeline-chaos` | `chaitin/safeline-*-g:9.4.3` | supporting services |

Shared data (config, rules, sockets, logs) lives in one 5 Gi volume (`safeline-data`), mounted with a different sub-path per component.

## Install

```bash
# 1. namespace + a random database password (the password never goes into git)
kubectl create namespace safeline
kubectl -n safeline create secret generic safeline-db --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 16)"

# 2. everything else
kubectl apply -f k8s/safeline.yaml
kubectl get pods -n safeline -w          # wait until all 7 pods are 1/1 Running (first start pulls ~2 GB of images)

# 3. one-time: cap nginx workers (see "Why" below)
kubectl exec -n safeline deploy/safeline-tengine -c tengine -- sh -c 'sed -i "s/^# worker_processes 4;/worker_processes 2;/" /etc/nginx/nginx.conf && nginx -s reload'
```

## First login

```bash
kubectl port-forward -n safeline svc/safeline-mgt 9443:1443        # keeps the console on localhost only
kubectl exec -it -n safeline deploy/safeline-mgt -c mgt -- resetadmin   # prints the admin username and a new password
```
Open **https://localhost:9443** (self-signed certificate, accept the warning) and log in with what `resetadmin` printed.

## Protect a site
In the console add a site whose upstream is a Kubernetes Service, for example `http://notes-app.notes.svc.cluster.local:80`,
listening on port 80 or 443 (the only ports exposed by `safeline-waf`; add more to that Service if you use other ports).
Send traffic through `svc/safeline-waf`, for example `kubectl port-forward -n safeline svc/safeline-waf 8080:80`.

## Status of this port
Tested on kind (Kubernetes 1.37): all 7 pods run stably, the console answers (`/api/open/health` returns `{"status":"ok"}`),
the whole stack uses roughly 1 GB of memory. **Not tested yet:** logging in, adding a protected site and blocking an attack.

## Why the manifests look the way they do (things that failed first)

| Symptom | Cause | What the manifest does |
|---|---|---|
| `bind: address already in use` on port 80 | `mgt`, `fvm` and `tengine` all listen on port 80; in compose they have separate addresses | one Deployment (own pod, own network) per component |
| `access forbidden by rule` in mgt, components fail | mgt's nginx only accepts internal `/inner` calls from one /24 (compose default `172.22.222`), set by env `SUBNET_PREFIX` | `SUBNET_PREFIX=10.244.1` = the pod range of the node that holds the volume |
| components cannot find each other | compose uses container names | one Service per component with exactly those names (headless) |
| `tengine` `OOMKilled` | nginx starts one worker per CPU core (12 here, ~80 Mi each) | `worker_processes 2;` (step 3) and a 2 Gi limit as headroom |
| pods on different nodes get different pod ranges | the shared volume is a node-local volume | `fvm` is pinned to `mycluster-worker2`; the other pods follow the volume |

If your volume lands on a different node, change `SUBNET_PREFIX` (in `safeline-mgt`) and the `nodeSelector` (in `safeline-fvm`) to that node's pod range and name:
`kubectl get pods -n safeline -o wide`.

## Uninstall
```bash
kubectl delete namespace safeline      # removes everything, including the volumes (rules and settings are lost)
```
