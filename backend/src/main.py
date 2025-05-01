from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import subprocess
import os
import asyncio
from .scanner import scan_projects  # Giữ nguyên import scanner
import re

app = FastAPI()
BASE_DIR = "/app/terraform-projects/"

# CORS config (giữ nguyên)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Giữ nguyên endpoint hiện có
@app.get("/projects")
async def get_projects():
    return scan_projects()

# Thêm model và endpoint mới cho Terraform
class TerraformCommand(BaseModel):
    command: str
    folders: List[str]

def clean_ansi_codes(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

@app.post("/terraform/execute")
async def execute_terraform(command: TerraformCommand):
    results = {}
    for folder in command.folders:
        full_path = os.path.join(BASE_DIR, folder)
        if not os.path.exists(full_path):
            results[folder] = {
                "success": False,
                "output": f"Error: Folder {full_path} not found"
            }
            continue
        
        try:
            process = await asyncio.create_subprocess_exec(
                "terraform",
                *command.command.split(),
                cwd=full_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            output_text = stdout.decode('utf-8') if process.returncode == 0 else stderr.decode('utf-8')
            cleaned_output = clean_ansi_codes(output_text)
            
            results[folder] = {
                "success": process.returncode == 0,
                "output": cleaned_output.strip()
            }
        except Exception as e:
            results[folder] = {
                "success": False,
                "output": f"Error: {str(e)}"
            }
    
    return {"status": "completed", "results": results}