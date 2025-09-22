# Django super simples (localhost, sem admin)

Rotas:
- `/signup/` — criar usuário
- `/login/`  — entrar
- `/logout/` — sair
- `/`        — home protegida

Como rodar:
```bash
cd django_super_simples
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/Mac:
# source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

Acesse http://127.0.0.1:8000/ — cadastre pelo `/signup/`.