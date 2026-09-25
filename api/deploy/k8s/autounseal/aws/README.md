# OpenBao auto-unseal · AWS KMS

🇺🇸 Wraps OpenBao's master key with a customer-managed AWS KMS key instead of
Shamir shares. Verified against
[openbao.org/docs/configuration/seal/awskms](https://openbao.org/docs/configuration/seal/awskms)
(v2.6.x docs) — see `seal.hcl` for the exact stanza this overlay ships.

🇧🇷 Envolve a master key do OpenBao com uma chave gerenciada pelo cliente no
AWS KMS em vez de shares Shamir. Verificado contra
[openbao.org/docs/configuration/seal/awskms](https://openbao.org/docs/configuration/seal/awskms)
(docs da v2.6.x) — veja `seal.hcl` para o stanza exato que este overlay traz.

## 1. Create the KMS key · Criar a chave no KMS

```sh
aws kms create-key --description "diagnos OpenBao auto-unseal" \
  --key-usage ENCRYPT_DECRYPT --key-spec SYMMETRIC_DEFAULT
aws kms create-alias --alias-name alias/diagnos-openbao-unseal --target-key-id <KeyId>
```

## 2. Minimal IAM permissions · Permissões IAM mínimas

🇺🇸 Attach this to the role `eks.amazonaws.com/role-arn` (below) assumes —
nothing wider; OpenBao only ever encrypts/decrypts the master key blob and
reads the key's metadata to validate it on startup.

🇧🇷 Anexe isto ao role que `eks.amazonaws.com/role-arn` (abaixo) assume —
nada mais amplo; o OpenBao só cifra/decifra o blob da master key e lê os
metadados da chave para validar na subida.

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

## 3. IRSA trust policy · Trust policy do IRSA

🇺🇸 The role above needs a trust policy scoped to this one ServiceAccount
(`openbao` in namespace `openbao`) so no other workload in the cluster can
assume it:

🇧🇷 O role acima precisa de uma trust policy restrita a este único
ServiceAccount (`openbao` no namespace `openbao`) para nenhum outro
workload do cluster conseguir assumi-lo:

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

## 4. Apply · Aplicar

```sh
# 🇺🇸 fill in seal.hcl's kms_key_id and the two REPLACE_ME values this
#    overlay patches (role ARN, region) before applying
# 🇧🇷 preencha o kms_key_id de seal.hcl e os dois REPLACE_ME que este
#    overlay aplica por patch (role ARN, region) antes de aplicar
kubectl apply -k deploy/k8s/autounseal/aws
```

## Reused by Compose · Reaproveitado pelo Compose

🇺🇸 Set `OPENBAO_SEAL=aws` in `deploy/compose/.env` and this exact `seal.hcl`
is bind-mounted into the Compose `openbao` service too — fill in the same
`AWS_REGION`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` variables in that
`.env` (no IRSA outside Kubernetes, so credentials go through the
environment instead).

🇧🇷 Defina `OPENBAO_SEAL=aws` no `deploy/compose/.env` e este mesmo
`seal.hcl` é montado no serviço `openbao` do Compose também — preencha as
mesmas variáveis `AWS_REGION`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`
naquele `.env` (sem IRSA fora do Kubernetes, então a credencial passa pelo
ambiente).
