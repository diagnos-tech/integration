# Exemplo: Subir um arquivo

[English](README.md) · **Português (Brasil)**

Cria uma pasta no drive do seu primeiro grupo concedido, sobe um arquivo de texto pequeno nela (nome e bytes selados neste processo), lista a pasta, baixa o arquivo de volta e confere que os bytes são idênticos.

> [!WARNING]
> Este exemplo **cria dados** no workspace. Use um descartável.

## Pré-requisitos

Python 3.11+, `pip install "diagnos[sdk]"`, e um token de conta de serviço em `DIAGNOS_TOKEN` (ou guardado pelo `diagnos login`) — veja [o índice dos exemplos](../README.pt-BR.md#antes-de-rodar-qualquer-um).

## Rodar

```sh
python main.py
```

## Saída esperada

No `stdout` (os ids mudam a cada execução):

```text
uploaded: hello-diagnos.txt (text/plain) node=node_2
folder has 1 file(s): hello-diagnos.txt
downloaded: 69 bytes match
```

Código de saída: `0`; `1` em erro do cofre ou se os bytes diferirem; `2` erro de configuração; `3` nenhum grupo concedido.

Para subir um diretório inteiro, veja [Arquivos](../../docs/guides/files.pt-BR.md).
