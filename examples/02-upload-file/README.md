# Example: Upload a file

**English** · [Português (Brasil)](README.pt-BR.md)

Creates a folder in the drive of your first granted group, uploads a small text file into it (its name and bytes are sealed in this process), lists the folder, downloads the file back and checks the bytes are identical.

> [!WARNING]
> This example **creates data** in the workspace. Use one you can throw away.

## Prerequisites

Python 3.11+, `pip install "diagnos[sdk]"`, a service account credential in `DIAGNOS_CREDENTIAL` and someone to approve the enrollment — see [the examples index](../README.md#before-you-run-any-of-them).

## Run

```sh
python main.py
```

## Expected output

On `stdout` (ids differ on every run):

```text
uploaded: hello-diagnos.txt (text/plain) node=node_2
folder has 1 file(s): hello-diagnos.txt
downloaded: 69 bytes match
```

Exit code: `0`; `1` on a vault error or if the bytes differ; `2` configuration error; `3` no group granted.

To upload a whole directory, see [Files](../../docs/guides/files.md).
