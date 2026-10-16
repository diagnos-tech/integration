# Exemplo: Pacientes

[English](README.md) · **Português (Brasil)**

Cria um paciente a partir de um `PatientRecord` tipado (com uma tag), lista todos os pacientes do grupo pelo resumo selado (nenhuma versão baixada) e lê o novo paciente de volta, decifrado.

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
patient created: doc_1 in sg_oncology
patients listed: 1 in sg_oncology
  doc_1  Jane
patient read: Jane Example, tags=['example'], version=ver_2
```

Código de saída: `0`; `1` em erro do cofre; `2` erro de configuração; `3` nenhum grupo concedido.

Atualizar, arquivar e escritas concorrentes: [Pacientes](../../docs/guides/patients.pt-BR.md).
