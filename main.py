from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from dotenv import load_dotenv
import hmac
import hashlib
import subprocess
import os
import logging
import json

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Carrega variáveis do .env (opcional, se estiver usando dotenv)
load_dotenv()

# Configurações principais
SECRET = os.getenv("SECRET_KEY")  # Deve corresponder ao segredo do webhook
APPS_DIR = os.getenv("APPS_DIR")  # Diretório onde estão os repositórios
ENV_DIR = os.getenv("ENV_DIR")

# Função para carregar variáveis de /etc/env.conf
def load_env_config():
    env_vars = {}
    try:
        with open(ENV_DIR, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
        logger.info(f"Variáveis de {ENV_DIR} carregadas com sucesso.")
        return env_vars
    except Exception as e:
        logger.error(f"Erro ao carregar {ENV_DIR}: {e}")
        return {}

# Carrega as variáveis uma vez no início
GLOBAL_ENV = {**os.environ, **load_env_config()}

# Verifica a assinatura do webhook
def verify_signature(body: bytes, signature: str):
    if not SECRET:
        logger.error("SECRET_KEY não definida!")
        return False
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", signature)

# Executa o script de deployment
def run_deployment_script(repo_name: str):
    project_path = os.path.join(APPS_DIR, repo_name)
    script_path = os.path.join(project_path, "deployment.sh")
    
    if not os.path.exists(script_path):
        logger.error(f"Script não encontrado: {script_path}")
        return

    try:
        # Combina o ambiente global com variáveis específicas do projeto (se necessário)
        process_env = {**GLOBAL_ENV, "REPO_NAME": repo_name}
        
        process = subprocess.run(
            ["/bin/bash", script_path],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True,
            env=process_env,  # Passa todas as variáveis para o subprocesso
        )
        logger.info(f"Deployment OK - {repo_name}\nSaída:\n{process.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro no deployment - {repo_name}\nErro:\n{e.stderr}")

# Endpoint do webhook
@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    # Verificação de segurança
    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    if not verify_signature(body_bytes, signature):
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    # Processa o payload do GitHub
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload inválido")

    # Verifica se é um push para a branch principal
    ref = payload.get("ref", "")
    if ref not in ["refs/heads/main", "refs/heads/master"]:
        return {"status": "ignorado - não é main/master"}

    # Obtém o nome do repositório
    repo_name = payload["repository"]["name"]
    
    # Dispara o deployment em background
    background_tasks.add_task(run_deployment_script, repo_name)
    
    return {"status": "deployment iniciado", "repositorio": repo_name}

# Endpoint de saúde (opcional)
@app.get("/health")
async def health_check():
    return {"status": "online"}