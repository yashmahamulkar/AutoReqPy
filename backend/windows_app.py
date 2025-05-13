from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import BaseModel, HttpUrl, ValidationError
from git import Repo
import os
import uuid
import subprocess
import shutil
from pathlib import Path
import logging
import platform
import time
import psutil
import gc
import sys
import ast
import argparse
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

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

CLONE_BASE_DIR = os.getenv("CLONE_BASE_DIR", "./cloned_repos")
Path(CLONE_BASE_DIR).mkdir(parents=True, exist_ok=True)

executor = ThreadPoolExecutor(max_workers=2)

class RepoInput(BaseModel):
    github_url: HttpUrl

    @classmethod
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

def get_imports_from_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            tree = ast.parse(f.read(), filename=filepath)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        return imports
    except Exception as e:
        logger.warning(f"Failed to parse {filepath}: {e}")
        return set()

def generate_requirements_manual(destination_path: str) -> str:
    imports = set()
    for root, _, files in os.walk(destination_path):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                imports.update(get_imports_from_file(filepath))
    return '\n'.join(f"{imp}>=0.0.0" for imp in sorted(imports)) or "# No imports detected"

def analyze_dependencies_with_gemini(requirements_content: str) -> str:
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key not set. Returning original requirements.")
        return requirements_content

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"""Given the following Python dependencies, generate a clean requirements.txt file that:
        1. Strictly remove duplicates any repeated dependencies.
        2. Resolves any version conflicts.
        3. Only includes necessary dependencies for the project.
        4. Formats the output strictly as a `requirements.txt` file, without any additional explanations.

        Input:
        {requirements_content}

        Output:
        ```requirements.txt
        [cleaned dependencies]
        """
        response = model.generate_content(prompt)
        logger.info(f"Gemini Analysis Response: {response.text}")
        return response.text
    except Exception as e:
        logger.error(f"Gemini analysis failed: {e}")
        return f"# Gemini analysis error: {str(e)}\n{requirements_content}"

def generate_requirements(destination_path: str) -> str:
    if not install_pipreqs():
        logger.error("Pipreqs not available, falling back to manual parsing")
        return generate_requirements_manual(destination_path)

    try:
        requirements_path = os.path.join(destination_path, "requirements.txt")
        result = subprocess.run(
            ["pipreqs", destination_path, "--force", "--savepath", requirements_path, "--ignore", ".git,tests,docs,build"],
            capture_output=True,
            text=True,
            timeout=60,
            shell=(platform.system() == "Windows")
        )

        if os.path.exists(requirements_path):
            with open(requirements_path, "r", encoding="utf-8") as f:
                requirements_content = f.read()

            logger.info(f"Requirements generated:\n{requirements_content}")
            gemini_analysis = analyze_dependencies_with_gemini(requirements_content)
            return gemini_analysis

        logger.warning(f"Pipreqs output: {result.stdout or result.stderr}")
        return generate_requirements_manual(destination_path)

    except subprocess.TimeoutExpired:
        logger.error("Pipreqs generation timed out, falling back to manual parsing")
        return generate_requirements_manual(destination_path)
    except UnicodeDecodeError as e:
        logger.error(f"UnicodeDecodeError in pipreqs: {e}, falling back to manual parsing")
        return generate_requirements_manual(destination_path)
    except Exception as e:
        logger.error(f"Pipreqs generation failed: {e}, falling back to manual parsing")
        return generate_requirements_manual(destination_path)

@app.route("/")
def a():
    return jsonify({"test": "test"}), 200

@app.route("/clone-repo/", methods=["POST"])
async def clone_repo():
    try:
        data = request.get_json()
        repo_input = RepoInput(github_url=data.get("github_url"))
    except (ValidationError, ValueError) as e:
        return jsonify({"error": f"Invalid input: {str(e)}"}), 400

    repo_url = str(repo_input.github_url)
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    unique_folder = f"{repo_name}_{uuid.uuid4().hex[:8]}"
    destination_path = os.path.join(CLONE_BASE_DIR, unique_folder)

    try:
        # Clone the repository
        repo = Repo.clone_from(repo_url, destination_path, depth=1, progress=None, no_checkout=False)
        repo.close()

        # Generate requirements
        requirements_content = generate_requirements(destination_path)

        # Schedule cleanup
        asyncio.create_task(asyncio.to_thread(comprehensive_cleanup, destination_path))

        return jsonify({"requirements.txt": requirements_content})

    except Exception as e:
        logger.error(f"Cloning operation failed: {str(e)}")
        asyncio.create_task(asyncio.to_thread(comprehensive_cleanup, destination_path))
        return jsonify({"error": f"Operation failed: {str(e)}"}), 400

def process_local_repo(local_path: str):
    if not os.path.isdir(local_path):
        logger.error(f"Provided path is not a valid directory: {local_path}")
        print(f"Error: {local_path} is not a valid directory.")
        return

    logger.info(f"Processing local repository at: {local_path}")
    try:
        requirements_content = generate_requirements(local_path)
        print("\nGenerated requirements.txt:\n")
        print(requirements_content)
    except Exception as e:
        logger.error(f"Failed to process local repository: {str(e)}")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dependency extractor for GitHub and local repositories")
    parser.add_argument('--local', type=str, help='Path to local Python project directory')
    parser.add_argument('--serve', action='store_true', help='Run the Flask server')
    args = parser.parse_args()

    if args.local:
        if not GEMINI_API_KEY:
            print("WARNING: Gemini API key not set. Output will be raw without cleanup.")
        process_local_repo(args.local)
    elif args.serve:
        if not GEMINI_API_KEY:
            print("WARNING: Gemini API key not set. Dependency analysis will be limited.")
        app.run(debug=True)
    else:
        parser.print_help()
