# Arquivos e pastas

[English](files.md) · **Português (Brasil)**

`vault.drives` guarda séries DICOM, imagens, vídeo e PDFs cifrados ponta a ponta, em pastas e ligados a exames. Cada
arquivo ganha a própria chave; o nome, o conteúdo e a cifragem própria da camada de armazenamento são selados
exatamente como o app web os sela, então um arquivo subido aqui abre no app web e vice-versa. O modelo — nós, grupos,
pendente e pronto — está em [Conceitos](concepts.pt-BR.md#arquivos-e-pastas-nós).

## Subir

Um **drive** é o conjunto de arquivos de um security group. Gravar precisa de um; ler só precisa do id do nó.

```python
from diagnos import Diagnos

vault = Diagnos()
drive = vault.drives.drive("sg_oncology")

node = drive.upload("scans/IM-0001.dcm")  # nome e tipo MIME a partir do path
print(node.node_id, node.status, node.mime_type, node.size)

note = drive.upload(b"bytes crus tambem funcionam", name="nota.txt")  # bytes precisam de nome
with open("report.pdf", "rb") as handle:
    pdf = drive.upload(handle)  # um arquivo aberto: o nome vem do handle
```

| Argumento | Padrão | |
|---|---|---|
| `name` | o nome de arquivo do path (ou do arquivo aberto) | obrigatório para `bytes` e streams anônimos; selado |
| `mime_type` | adivinhado pelo nome; `.dcm` é `application/dicom` | enviado em claro — é como o cofre classifica DICOM, imagem e vídeo |
| `exam_id` | nenhum | liga o arquivo a um exame |
| `parent_id` | nenhum | a pasta onde colocá-lo |

`upload()` retorna quando o arquivo está confirmado: o nó está `ready`.

> [!TIP]
> Passe um path ou `bytes` quando puder. O tamanho precisa ser conhecido antes de cifrar — o cofre assina cada upload
> para um número exato de bytes — então qualquer outro stream é antes copiado para um arquivo temporário, em texto
> claro, e removido depois do upload.

### Vários arquivos de uma vez

```python
from diagnos import UploadSource

folder_id = drive.create_folder("TC 2026-09-01")
nodes = drive.upload_many(
    ["scans/IM-0001.dcm", "scans/IM-0002.dcm", UploadSource(b"...", name="notas-da-serie.txt")],
    parent_id=folder_id,
)
print([drive.name_of(node) for node in nodes])  # na ordem de entrada, todos prontos
```

`upload_many` reserva até 100 arquivos por ida e volta e devolve os nós na ordem de entrada. Ele bloqueia até cada
lote terminar; ainda não existe callback de progresso por byte.

### Como arquivos grandes viajam

Você nunca escolhe; o cofre escolhe, pelo tamanho:

| Tamanho | Como sobe |
|---|---|
| até 64 MiB | um `PUT` assinado, confirmado junto com o resto do lote |
| acima de 64 MiB, até 50 GiB | partes de 32 MiB, assinadas em ondas de até 200 conforme o upload avança |

Um upload multipart que falha no meio é abortado, para o cofre liberar o espaço reservado na hora; uma reserva
abandonada expira depois de 6 horas. O corpo é cifrado em frames de 1 MiB enquanto flui, então a memória fica
estável qualquer que seja o tamanho do arquivo. O [PROTOCOL.pt-BR.md §9](../PROTOCOL.pt-BR.md#9-arquivos-e-pastas-nós)
tem o layout dos bytes.

## Pastas

```python
series = drive.create_folder("Série 2", parent_id=folder_id)  # aninhada
drive.upload("scans/IM-0002.dcm", parent_id=series)
```

`create_folder` devolve o id do nó da pasta nova. O cofre só vê nomes selados, então não distingue duas pastas com o
mesmo nome: chamar duas vezes cria duas pastas. Pastas ficam prontas na hora — não têm conteúdo.

## Listar

```python
for child in drive.iter_all(parent_id=folder_id):  # uma pasta deste grupo
    print(drive.name_of(child), child.kind, child.size)

for item in vault.drives.iter_all(include_pending=True):  # todo grupo que esta sessão pode listar
    print(item.security_group_id, item.status, item.node_id)

page = vault.drives.list(security_group="sg_oncology", limit=50)  # uma página
```

`drive.list()`/`iter_all()` percorrem um grupo; `vault.drives.list()`/`iter_all()` percorrem todo grupo que esta
sessão pode listar, filtrados por `security_group`, `exam_id`, `parent_id` ou `include_pending`. As linhas são
`DriveNode`s — só metadado. Os nomes ficam selados até você pedir: `name_of(node)` abre um, então uma página de mil
arquivos não custa nenhuma decifragem que você não quis.

> [!WARNING]
> Um nome é o que quem subiu selou, e o app web sela um **caminho relativo** ali (`exames/2026/IM-0001.dcm`). Nunca o
> use como caminho local do jeito que vem: pegue o último segmento, como a CLI e a API fazem.

`vault.drives.get(node_id)` devolve o metadado de um arquivo pronto; uma pasta ou um upload pendente responde
`NotFoundError` — não há nada para baixar.

## Baixar

```python
data = vault.drives.download(node.node_id)  # o arquivo inteiro, decifrado, na RAM
vault.drives.download(node.node_id, "IM-0001.dcm")  # direto para um arquivo, um pedaço na RAM por vez

with open("copia.dcm", "wb") as out:
    for chunk in vault.drives.iter_download(node.node_id):  # faça o stream você mesmo
        out.write(chunk)
```

`iter_download` decifra de forma preguiçosa: os primeiros bytes chegam a você antes de os últimos saírem do
armazenamento, e nada maior que um frame de 1 MiB fica guardado. Todo frame é autenticado; um arquivo adulterado ou
truncado lança `CryptoError` em vez de devolver bytes danificados.

## O que o cofre vê de um arquivo

O id do nó, o grupo, o exame e a pasta a que está ligado, o tipo MIME, o tamanho (do corpo cifrado, que o cofre mede e
cobra) e os horários. Nunca o nome, nunca o conteúdo. A lista completa está no [modelo de
segurança](security.pt-BR.md#o-que-o-cofre-vê).

## O que ainda não está aqui

- Apagar, mover e renomear ainda não têm rota externa.
- Miniaturas e transcodificações para a web (`optimized_variants`) só são produzidas para arquivos cuja chave também é
  custodiada para o processador de mídia do cofre, o que nem o app web nem o SDK fazem hoje.
- Sem callback de progresso por byte.

Detalhes e as questões ainda abertas do lado do cofre: [COMPATIBILITY.pt-BR.md](../COMPATIBILITY.pt-BR.md#arquivos-e-pastas).
