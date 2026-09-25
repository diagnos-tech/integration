# OpenBao auto-unseal · GCP Cloud KMS

🇺🇸 Wraps OpenBao's master key with a Cloud KMS key. Verified against
[openbao.org/docs/configuration/seal/gcpckms](https://openbao.org/docs/configuration/seal/gcpckms)
(v2.6.x docs) — see `seal.hcl` for the exact stanza this overlay ships.

🇧🇷 Envolve a master key do OpenBao com uma chave do Cloud KMS. Verificado
contra
[openbao.org/docs/configuration/seal/gcpckms](https://openbao.org/docs/configuration/seal/gcpckms)
(docs da v2.6.x) — veja `seal.hcl` para o stanza exato que este overlay
traz.

## 1. Create the key ring and key · Criar o key ring e a chave

```sh
gcloud kms keyrings create diagnos-openbao --location=<region>
gcloud kms keys create unseal --location=<region> --keyring=diagnos-openbao \
  --purpose=encryption
```

## 2. Minimal IAM role · Papel IAM mínimo

🇺🇸 Grant the GSA below exactly `roles/cloudkms.cryptoKeyEncrypterDecrypter`
on this one key — not on the key ring, not project-wide:

🇧🇷 Conceda à GSA abaixo exatamente `roles/cloudkms.cryptoKeyEncrypterDecrypter`
nesta única chave — não no key ring, não no projeto inteiro:

```sh
gcloud kms keys add-iam-policy-binding unseal \
  --location=<region> --keyring=diagnos-openbao \
  --member="serviceAccount:<gsa-name>@<project>.iam.gserviceaccount.com" \
  --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"
```

## 3. Workload Identity binding · Vínculo do Workload Identity

🇺🇸 Bind the GSA to the `openbao` KSA (namespace `openbao`) so the
annotation `../kustomization.yaml` patches onto the ServiceAccount actually
resolves to ambient credentials:

🇧🇷 Vincule a GSA à KSA `openbao` (namespace `openbao`) para a anotação que
`../kustomization.yaml` aplica por patch no ServiceAccount de fato resolver
para credencial ambiente:

```sh
gcloud iam service-accounts add-iam-policy-binding \
  <gsa-name>@<project>.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:<project>.svc.id.goog[openbao/openbao]"
```

## 4. Apply · Aplicar

```sh
# 🇺🇸 fill in seal.hcl's project/region/key_ring/crypto_key and the
#    REPLACE_ME GSA annotation before applying
# 🇧🇷 preencha o project/region/key_ring/crypto_key de seal.hcl e a
#    anotação REPLACE_ME da GSA antes de aplicar
kubectl apply -k deploy/k8s/autounseal/gcp
```

## Reused by Compose · Reaproveitado pelo Compose

🇺🇸 Set `OPENBAO_SEAL=gcp` in `deploy/compose/.env`. There is no Workload
Identity outside GKE, so point `GOOGLE_APPLICATION_CREDENTIALS` at a
service-account JSON key mounted into the container instead — see the
comment in that `.env.example`.

🇧🇷 Defina `OPENBAO_SEAL=gcp` no `deploy/compose/.env`. Não existe Workload
Identity fora do GKE, então aponte `GOOGLE_APPLICATION_CREDENTIALS` para uma
chave JSON de service account montada no container em vez disso — veja o
comentário naquele `.env.example`.
