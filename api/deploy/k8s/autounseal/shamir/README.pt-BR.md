# OpenBao auto-unseal · Shamir (manual, o fallback)

[English](README.md) · **Português (Brasil)**

Não é auto-unseal de fato — é o fallback que o próprio OpenBao usa por padrão quando nenhum stanza `seal` está
configurado. Todo reinício do pod `openbao-0` exige um humano rodando `bao operator unseal` três vezes (o threshold
padrão) com três das cinco chaves que o script de `bootstrap-configmap.yaml` imprimiu no init inicial. Sem KMS, sem
IAM extra de nuvem para configurar — e sem jeito de reiniciar sem supervisão, que é exatamente por isso que os
outros cinco overlays desta pasta existem.

## Aplicar

```sh
kubectl apply -k deploy/k8s/autounseal/shamir   # igual a `-k deploy/k8s/openbao`
```

## Depois de todo reinício

```sh
kubectl exec -n openbao -it openbao-0 -- bao operator unseal <key 1 of 3>
kubectl exec -n openbao -it openbao-0 -- bao operator unseal <key 2 of 3>
kubectl exec -n openbao -it openbao-0 -- bao operator unseal <key 3 of 3>
```

Só vale escolher para um cluster genuinamente descartável, ou um onde um operador já é acionado a cada reinício do
OpenBao de qualquer jeito. Para qualquer coisa que a própria liveness probe do pod possa reiniciar sem supervisão,
escolha um backend de auto-unseal de verdade.

## Reaproveitado pelo Compose

`OPENBAO_SEAL=shamir` é o padrão do `deploy/compose/.env` — `openbao-bootstrap` ali automatiza exatamente este passo
manual guardando as chaves de unseal num volume local, uma conveniência só-para-staging que o cabeçalho de
`deploy/compose/openbao/bootstrap.sh` avisa em voz alta. Essa conveniência não existe aqui: este overlay é unseal na
mão, sem meio-termo.
