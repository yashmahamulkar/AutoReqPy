from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import os
from git import Repo
import uuid
import uvicorn

app = FastAPI()


CLONE_BASE_DIR = "./cloned_repos"
os.makedirs(CLONE_BASE_DIR, exist_ok=True)


class RepoInput(BaseModel):
    github_url: HttpUrl


@app.post("/clone-repo/")
async def clone_repo(input: RepoInput):
    repo_url = str(input.github_url)  # Convert HttpUrl to string
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    unique_folder = f"{repo_name}_{uuid.uuid4().hex[:8]}"
    destination_path = os.path.join(CLONE_BASE_DIR, unique_folder)

    try:
        Repo.clone_from(repo_url, destination_path)
        return {
            "message": "Repository cloned successfully",
            "cloned_to": destination_path
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cloning failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
