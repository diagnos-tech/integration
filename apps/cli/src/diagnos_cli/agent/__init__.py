"""🇺🇸 The session agent: one unlocked session, kept in the SDK's locked memory, reused by every later command.

Each `diagnos` invocation is a new process, and an SDK session lives in the
RAM of the process that unlocked it — so without help, every command would
enroll again. `diagnos login` starts an agent instead: a background process
that unlocks once and keeps the session in the Rust enclave's locked,
non-dumpable memory. Later commands do not receive the session. They send
their arguments to the agent over a Unix socket and the agent runs the
command itself, streaming its output back, so the keys never leave that
one process. Nothing is written to disk, and no OS keychain is involved.

Who may talk to it: the socket lives in a directory only the user can
enter (`0700`, checked on every use), and on Linux the agent also checks the
peer's uid. The agent locks the session and exits on `diagnos logout`, after
`DIAGNOS_AGENT_IDLE_MINUTES` without a command (8 hours by default), or on
`SIGTERM`. `DIAGNOS_AGENT=off` keeps every command in its own process, as
before.

Layout: `dispatch` decides agent-or-here before parsing; `paths` names and
guards the socket; `protocol` is the wire; `client` is the command side;
`server` is the accept loop; `host` owns the one `Diagnos`; `streams` are
the `sys.stdout`/`stderr`/`stdin` stand-ins; `__main__` is the process.

🇧🇷 O agente de sessão: uma sessão desbloqueada, guardada na memória travada do SDK, reaproveitada por todo
comando seguinte.

Cada invocação de `diagnos` é um processo novo, e uma sessão do SDK vive na
RAM do processo que a desbloqueou — então, sem ajuda, todo comando faria
enrollment de novo. O `diagnos login` sobe um agente no lugar: um processo em
segundo plano que desbloqueia uma vez e guarda a sessão na memória travada e
fora de core dump do enclave Rust. Os comandos seguintes não recebem a
sessão. Eles mandam os argumentos ao agente por um socket Unix e o agente
roda o comando ele mesmo, transmitindo a saída de volta, então as chaves
nunca saem daquele único processo. Nada é gravado em disco, e nenhum
keychain do sistema operacional entra.

Quem pode falar com ele: o socket fica num diretório em que só o usuário
entra (`0700`, conferido a cada uso), e no Linux o agente também confere o
uid de quem conecta. O agente trava a sessão e sai no `diagnos logout`,
depois de `DIAGNOS_AGENT_IDLE_MINUTES` sem comando (8 horas por padrão), ou
num `SIGTERM`. `DIAGNOS_AGENT=off` mantém cada comando no próprio processo,
como antes.

Organização: `dispatch` decide agente-ou-aqui antes de interpretar; `paths`
nomeia e protege o socket; `protocol` é o fio; `client` é o lado do comando;
`server` é o laço de accept; `host` é dono da única `Diagnos`; `streams` são
os substitutos de `sys.stdout`/`stderr`/`stdin`; `__main__` é o processo.
"""
