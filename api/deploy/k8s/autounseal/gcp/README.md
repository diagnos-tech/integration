# OpenBao auto-unseal · GCP Cloud KMS

**English** · [Português (Brasil)](README.pt-BR.md)

Wraps OpenBao's master key with a Cloud KMS key. Verified against
[openbao.org/docs/configuration/seal/gcpckms](https://openbao.org/docs/configuration/seal/gcpckms) (v2.6.x docs) —
see `seal.hcl` for the exact stanza this overlay ships.

## 1. Create the key ring and key

```sh
gcloud kms keyrings create diagnos-openbao --location=<region>
gcloud kms keys create unseal --location=<region> --keyring=diagnos-openbao \
  --purpose=encryption
```

## 2. Minimal IAM role

Grant the GSA below exactly `roles/cloudkms.cryptoKeyEncrypterDecrypter` on this one key — not on the key ring, not
project-wide:

```sh
gcloud kms keys add-iam-policy-binding unseal \
  --location=<region> --keyring=diagnos-openbao \
  --member="serviceAccount:<gsa-name>@<project>.iam.gserviceaccount.com" \
  --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"
```

## 3. Workload Identity binding

Bind the GSA to the `openbao` KSA (namespace `openbao`) so the annotation `../kustomization.yaml` patches onto the
ServiceAccount actually resolves to ambient credentials:

```sh
gcloud iam service-accounts add-iam-policy-binding \
  <gsa-name>@<project>.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:<project>.svc.id.goog[openbao/openbao]"
```

## 4. Apply

```sh
# fill in seal.hcl's project/region/key_ring/crypto_key and the
# REPLACE_ME GSA annotation before applying
kubectl apply -k deploy/k8s/autounseal/gcp
```

## Reused by Compose

Set `OPENBAO_SEAL=gcp` in `deploy/compose/.env`. There is no Workload Identity outside GKE, so point
`GOOGLE_APPLICATION_CREDENTIALS` at a service-account JSON key mounted into the container instead — see the comment
in that `.env.example`.
