# OpenBao auto-unseal · AWS KMS

**English** · [Português (Brasil)](README.pt-BR.md)

Wraps OpenBao's master key with a customer-managed AWS KMS key instead of Shamir shares. Verified against
[openbao.org/docs/configuration/seal/awskms](https://openbao.org/docs/configuration/seal/awskms) (v2.6.x docs) —
see `seal.hcl` for the exact stanza this overlay ships.

## 1. Create the KMS key

```sh
aws kms create-key --description "diagnos OpenBao auto-unseal" \
  --key-usage ENCRYPT_DECRYPT --key-spec SYMMETRIC_DEFAULT
aws kms create-alias --alias-name alias/diagnos-openbao-unseal --target-key-id <KeyId>
```

## 2. Minimal IAM permissions

Attach this to the role `eks.amazonaws.com/role-arn` (below) assumes — nothing wider; OpenBao only ever
encrypts/decrypts the master key blob and reads the key's metadata to validate it on startup.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["kms:Encrypt", "kms:Decrypt", "kms:DescribeKey"],
    "Resource": "arn:aws:kms:<region>:<account-id>:key/<key-id>"
  }]
}
```

## 3. IRSA trust policy

The role above needs a trust policy scoped to this one ServiceAccount (`openbao` in namespace `openbao`) so no
other workload in the cluster can assume it:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::<account-id>:oidc-provider/<eks-oidc-issuer>" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "<eks-oidc-issuer>:sub": "system:serviceaccount:openbao:openbao"
      }
    }
  }]
}
```

## 4. Apply

```sh
# fill in seal.hcl's kms_key_id and the two REPLACE_ME values this
# overlay patches (role ARN, region) before applying
kubectl apply -k deploy/k8s/autounseal/aws
```

## Reused by Compose

Set `OPENBAO_SEAL=aws` in `deploy/compose/.env` and this exact `seal.hcl` is bind-mounted into the Compose `openbao`
service too — fill in the same `AWS_REGION`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` variables in that `.env` (no
IRSA outside Kubernetes, so credentials go through the environment instead).
