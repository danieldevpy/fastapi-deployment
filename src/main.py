from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
import hmac
import hashlib
import subprocess
import os
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configurações
SECRET = os.getenv("SECRET_KEY")  # Mesma do webhook
APPS_DIR = os.getenv("APPS_DIR")

def verify_signature(body: bytes, signature: str):
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", signature)

async def run_deployment_script(repo_name: str):
    project_path = os.path.join(APPS_DIR, repo_name)
    script_path = os.path.join(project_path, "deployment.sh")
    
    if not os.path.exists(script_path):
        logger.error(f"Script não encontrado: {script_path}")
        return

    try:
        process = subprocess.run(
            ["bash", "-c", script_path],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Deployment OK - {repo_name}\nSaída:\n{process.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro no deployment - {repo_name}\nErro:\n{e.stderr}")

@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    # Verificação de segurança
    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    if not verify_signature(body_bytes, signature):
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    # Processar payload
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload inválido")

    # Verificar se é push na master
    if payload.get("ref") != "refs/heads/master":
        return {"status": "ignorado - não é master"}

    # Obter nome do repositório
    repo_name = payload["repository"]["name"]
    
    # Adicionar tarefa em segundo plano
    background_tasks.add_task(run_deployment_script, repo_name)
    
    return {"status": "deployment iniciado", "repositorio": repo_name}