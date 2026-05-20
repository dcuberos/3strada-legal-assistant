import sys
import os

# Importar torch antes do chainlit para evitar WinError 1114 no Windows.
# O Chainlit usa exec_module num contexto onde as DLLs do torch não conseguem
# inicializar. Ao importar aqui primeiro, torch fica em sys.modules e o
# _load_dll_libraries() não volta a correr quando o chainlit carregar app.py.
import torch  # noqa: F401

from chainlit.cli import cli

if __name__ == '__main__':
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
    sys.argv = ['chainlit', 'run', app_path]
    cli(standalone_mode=True)
