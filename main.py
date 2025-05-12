from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl, validator
from git import Repo
import os
import uuid
import uvicorn
import subprocess
import shutil
from pathlib import Path
import logging
import platform
import time
import psutil
import gc
import sys
from dotenv import load_dotenv
import google.generativeai as genai
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('repo_cloner.log')
    ]
)
logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("Gemini API Key not found. Some features will be limited.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="GitHub Repository Cloner")

# Use environment variable for base directory or default
CLONE_BASE_DIR = os.getenv("CLONE_BASE_DIR", "./cloned_repos")
Path(CLONE_BASE_DIR).mkdir(parents=True, exist_ok=True)

# Initialize ThreadPoolExecutor for background tasks
executor = ThreadPoolExecutor(max_workers=2)

class RepoInput(BaseModel):
    github_url: HttpUrl

    @validator('github_url')
    def validate_github_url(cls, v):
        url_str = str(v)
        if not (url_str.startswith("https://github.com/") and
                (url_str.endswith(".git") or url_str.rstrip("/").count("/") >= 2)):
            raise ValueError("Invalid GitHub repository URL")
        return v

def safe_terminate_process(proc):
    try:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except psutil.TimeoutExpired:
            proc.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
        pass

def comprehensive_cleanup(destination_path: str):
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            gc.collect()
            if os.path.exists(destination_path):
                open_handles = []
                for proc in psutil.process_iter(['pid', 'name', 'open_files']):
                    try:
                        for open_file in proc.open_files() or []:
                            if destination_path in str(open_file.path):
                                open_handles.append((proc.pid, proc.name(), open_file.path))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                if open_handles:
                    logger.warning(f"Open handles found: {open_handles}")
                    for pid, _, _ in open_handles:
                        try:
                            proc = psutil.Process(pid)
                            safe_terminate_process(proc)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                if platform.system() == "Windows":
                    subprocess.run(['taskkill', '/F', '/IM', 'git.exe'],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                
                shutil.rmtree(destination_path, ignore_errors=True)
                
                if os.path.exists(destination_path):
                    for root, dirs, files in os.walk(destination_path, topdown=False):
                        for name in files:
                            try:
                                os.chmod(os.path.join(root, name), 0o666)
                                os.unlink(os.path.join(root, name))
                            except Exception:
                                pass
                        for name in dirs:
                            try:
                                os.rmdir(os.path.join(root, name))
                            except Exception:
                                pass
                    os.rmdir(destination_path)
            return
        except Exception as e:
            logger.error(f"Cleanup attempt {attempt + 1} failed: {e}")
            time.sleep(1)
    logger.error(f"Failed to clean up {destination_path} after {max_attempts} attempts")

def install_pipreqs():
    try:
        import pipreqs
        return True
    except ImportError:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pipreqs'])
            return True
        except Exception as e:
            logger.error(f"Failed to install pipreqs: {e}")
            return False

def analyze_dependencies_with_gemini(requirements_content: str) -> str:
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key not set. Returning original requirements.")
        return requirements_content

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"""Given the following Python dependencies, generate a clean requirements.txt file with:
1. Deduplicated dependencies
2. Resolved version conflicts
3. Only include necessary dependencies
4. Format as requirements.txt

Input:
{requirements_content}

Output format:
```requirements.txt
[cleaned dependencies]
```"""
        
        response = model.generate_content(prompt)
        logger.info(f"Gemini Analysis Response: {response.text}")
        return response.text
    except Exception as e:
        logger.error(f"Gemini analysis failed: {e}")
        return f"# Gemini analysis error: {str(e)}\n{requirements_content}"

def generate_requirements(destination_path: str) -> str:
    if not install_pipreqs():
        try:
            setup_file = Path(destination_path) / 'setup.py'
            pyproject_file = Path(destination_path) / 'pyproject.toml'
            
            if setup_file.exists():
                result = subprocess.run(
                    [sys.executable, str(setup_file), '--name'],
                    capture_output=True,
                    text=True,
                    cwd=destination_path
                )
                if result.returncode == 0:
                    logger.info("Dependencies extracted from setup.py")
                    return result.stdout.strip()
            
            elif pyproject_file.exists():
                logger.info("pyproject.toml found, manual parsing would be needed")
                return "# Please manually check pyproject.toml for dependencies"
        
        except Exception as e:
            logger.error(f"Fallback requirements generation failed: {e}")
        
        return "# Unable to generate requirements automatically"

    try:
        requirements_path = os.path.join(destination_path, "requirements.txt")
        result = subprocess.run(
            ["pipreqs", destination_path, "--force", "--savepath", requirements_path],
            capture_output=True,
            text=True,
            timeout=30,
            shell=(platform.system() == "Windows")
        )

        if os.path.exists(requirements_path):
            with open(requirements_path, "r") as f:
                requirements_content = f.read()
            
            logger.info(f"Requirements generated:\n{requirements_content}")
            gemini_analysis = analyze_dependencies_with_gemini(requirements_content)
            return gemini_analysis
        
        logger.warning(f"Pipreqs output: {result.stdout or result.stderr}")
        return result.stdout or result.stderr or "# No requirements detected"
    
    except subprocess.TimeoutExpired:
        logger.error("Pipreqs generation timed out")
        return "# Requirements generation timed out"
    except Exception as e:
        logger.error(f"Pipreqs generation failed: {e}")
        return f"# Requirements generation error: {str(e)}"

@app.post("/clone-repo/")
async def clone_repo(input: RepoInput):
    repo_url = str(input.github_url)
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    unique_folder = f"{repo_name}_{uuid.uuid4().hex[:8]}"
    destination_path = os.path.join(CLONE_BASE_DIR, unique_folder)

    try:
        # Clone the repository
        repo = Repo.clone_from(repo_url, destination_path, depth=1, progress=None, no_checkout=False)
        repo.close()

        # Generate requirements
        requirements_content = generate_requirements(destination_path)

        # Schedule cleanup in the background
        asyncio.create_task(asyncio.to_thread(comprehensive_cleanup, destination_path))

        # Return the Gemini response immediately
        return {"requirements.txt": requirements_content}
    
    except Exception as e:
        logger.error(f"Cloning operation failed: {str(e)}")
        # Ensure cleanup runs even if there's an error
        asyncio.create_task(asyncio.to_thread(comprehensive_cleanup, destination_path))
        raise HTTPException(status_code=400, detail=f"Operation failed: {str(e)}")

if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("WARNING: Gemini API key not set. Dependency analysis will be limited.")
    uvicorn.run(app, host="0.0.0.0", port=8000)