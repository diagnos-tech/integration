# Exemplo: Exames

[English](README.md) · **Português (Brasil)**

Cria um paciente e um exame dele com laudo (`report_lexical` e `report_html`, para o editor web abrir), sobe um arquivo ligado ao exame, lê o exame de volta e o acha entre os exames do paciente.

Compartilhar um laudo por link não está no SDK: crie o link no app web. O visualizador público de links é uma rota do cofre para quem recebe o link, não uma chamada do SDK.

> [!WARNING]
> Este exemplo **cria dados** no workspace. Use um descartável.

## Pré-requisitos

Python 3.11+, `pip install "diagnos[sdk]"`, uma credencial de conta de serviço em `DIAGNOS_CREDENTIAL` e alguém para aprovar o enrollment — veja [o índice dos exemplos](../README.pt-BR.md#antes-de-rodar-qualquer-um).

## Rodar

```sh
python main.py
```

## Saída esperada

No `stdout` (os ids mudam a cada execução):

```text
exam created: doc_3 for patient doc_1
file attached: node_5 -> exam doc_3
exam read: Chest X-ray (CR), report: <p>No acute findings. Heart size within normal limits.</p>
exams of the patient: 1
```

Código de saída: `0`; `1` em erro do cofre; `2` erro de configuração; `3` nenhum grupo concedido.

Os campos do registro e o laudo: [Exames](../../docs/guides/exams.pt-BR.md).
