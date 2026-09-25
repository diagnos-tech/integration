# OpenBao auto-unseal · Shamir (manual, the fallback)

🇺🇸 Not auto-unseal at all — the fallback OpenBao itself defaults to when
no `seal` stanza is configured. Every restart of the `openbao-0` pod
requires a human to run `bao operator unseal` three times (the default
threshold) with three of the five keys `bootstrap-configmap.yaml`'s script
printed at first init. No KMS, no extra cloud IAM to set up — and no way
to restart unattended, which is exactly why the other five overlays in
this directory exist.

🇧🇷 Não é auto-unseal de fato — é o fallback que o próprio OpenBao usa por
padrão quando nenhum stanza `seal` está configurado. Todo reinício do pod
`openbao-0` exige um humano rodando `bao operator unseal` três vezes (o
threshold padrão) com três das cinco chaves que o script de
`bootstrap-configmap.yaml` imprimiu no init inicial. Sem KMS, sem IAM extra
de nuvem para configurar — e sem jeito de reiniciar sem supervisão, que é
exatamente por isso que os outros cinco overlays desta pasta existem.

## Apply · Aplicar

```sh
kubectl apply -k deploy/k8s/autounseal/shamir   # 🇺🇸 same as `-k deploy/k8s/openbao` · 🇧🇷 igual a `-k deploy/k8s/openbao`
```

## After every restart · Depois de todo reinício

```sh
kubectl exec -n openbao -it openbao-0 -- bao operator unseal <key 1 of 3>
kubectl exec -n openbao -it openbao-0 -- bao operator unseal <key 2 of 3>
kubectl exec -n openbao -it openbao-0 -- bao operator unseal <key 3 of 3>
```

🇺🇸 Only worth choosing for a genuinely disposable cluster, or one where an
operator is already paged for every OpenBao restart regardless. For
anything a pod's own liveness probe might restart unattended, pick a real
auto-unseal backend instead.

🇧🇷 Só vale escolher para um cluster genuinamente descartável, ou um onde
um operador já é acionado a cada reinício do OpenBao de qualquer jeito.
Para qualquer coisa que a própria liveness probe do pod possa reiniciar
sem supervisão, escolha um backend de auto-unseal de verdade.

## Reused by Compose · Reaproveitado pelo Compose

🇺🇸 `OPENBAO_SEAL=shamir` is `deploy/compose/.env`'s default —
`openbao-bootstrap` there automates exactly this manual step by keeping
the unseal keys on a local volume, which is a staging-only convenience
`deploy/compose/openbao/bootstrap.sh`'s header warns about loudly. That
convenience does not exist here: this overlay is unseal-by-hand, full stop.

🇧🇷 `OPENBAO_SEAL=shamir` é o padrão do `deploy/compose/.env` —
`openbao-bootstrap` ali automatiza exatamente este passo manual guardando
as chaves de unseal num volume local, uma conveniência só-para-staging que
o cabeçalho de `deploy/compose/openbao/bootstrap.sh` avisa em voz alta. Essa
conveniência não existe aqui: este overlay é unseal na mão, sem meio-termo.
