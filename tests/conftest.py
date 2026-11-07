import os
import tempfile

# Os testes nunca devem escrever no histórico real (analises/ do repositório).
os.environ.setdefault("DADOS_DIR", tempfile.mkdtemp(prefix="leilaoia_testes_"))
