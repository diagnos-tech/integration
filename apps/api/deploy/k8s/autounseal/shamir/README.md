# OpenBao auto-unseal · Shamir (manual, the fallback)

**English** · [Português (Brasil)](README.pt-BR.md)

Not auto-unseal at all — the fallback OpenBao itself defaults to when no `seal` stanza is configured. Every restart
of the `openbao-0` pod requires a human to run `bao operator unseal` three times (the default threshold) with three
of the five keys `bootstrap-configmap.yaml`'s script printed at first init. No KMS, no extra cloud IAM to set up —
and no way to restart unattended, which is exactly why the other five overlays in this directory exist.

## Apply

```sh
kubectl apply -k deploy/k8s/autounseal/shamir   # same as `-k deploy/k8s/openbao`
```

## After every restart

```sh
kubectl exec -n openbao -it openbao-0 -- bao operator unseal <key 1 of 3>
kubectl exec -n openbao -it openbao-0 -- bao operator unseal <key 2 of 3>
kubectl exec -n openbao -it openbao-0 -- bao operator unseal <key 3 of 3>
```

Only worth choosing for a genuinely disposable cluster, or one where an operator is already paged for every OpenBao
restart regardless. For anything a pod's own liveness probe might restart unattended, pick a real auto-unseal
backend instead.

## Reused by Compose

`OPENBAO_SEAL=shamir` is `deploy/compose/.env`'s default — `openbao-bootstrap` there automates exactly this manual
step by keeping the unseal keys on a local volume, which is a staging-only convenience
`deploy/compose/openbao/bootstrap.sh`'s header warns about loudly. That convenience does not exist here: this
overlay is unseal-by-hand, full stop.
