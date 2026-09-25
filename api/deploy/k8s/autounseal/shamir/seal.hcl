# 🇺🇸 Intentionally empty of a `seal` block: Shamir is OpenBao's built-in
# default whenever no `seal` stanza is present in its config directory, so
# "configure Shamir" is "add no seal stanza at all". This file exists only
# so `deploy/compose/docker-compose.yml`'s `OPENBAO_SEAL=shamir` bind mount
# (`../k8s/autounseal/${OPENBAO_SEAL:-shamir}/seal.hcl`) has something to
# mount without a special case, and so this directory can hold the README
# that explains the manual-unseal tradeoff for this, the fallback provider.
# 🇧🇷 De propósito sem bloco `seal`: Shamir é o padrão embutido do OpenBao
# sempre que nenhum stanza `seal` está presente no diretório de config,
# então "configurar Shamir" é "não somar stanza de seal nenhuma". Este
# arquivo existe só para o bind mount de `OPENBAO_SEAL=shamir` do
# `deploy/compose/docker-compose.yml`
# (`../k8s/autounseal/${OPENBAO_SEAL:-shamir}/seal.hcl`) ter o que montar
# sem caso especial, e para este diretório poder guardar o README que
# explica o tradeoff de unseal manual deste, o provedor de fallback.
