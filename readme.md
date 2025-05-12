# AutoReqPy

**AutoReqPy** is a Python-powered utility that generates clean and accurate `requirements.txt` files for Python projects. It intelligently analyzes your codebase to identify only the dependencies actively used, eliminating unused package bloat. The application features a Flask backend for processing and a Vite-based frontend for an intuitive user interface.

## Features

### Intelligent Dependency Analysis
- **Codebase Scanning**: Analyzes Python projects to detect imported libraries, ensuring only used dependencies are included in the `requirements.txt`.
- **Pipreqs Integration**: Uses `pipreqs` to generate an initial dependency list by scanning Python files, streamlining dependency identification.
- **Gemini API Optimization**: Leverages the Gemini API to:
  - Deduplicate repeated dependencies.
  - Resolve version conflicts for compatibility.
  - Remove unused or unnecessary packages, producing a minimal, accurate `requirements.txt`.
- **Fallback Mechanism**: Returns raw `pipreqs` output if the Gemini API key is unavailable, maintaining functionality without AI optimization.

### Efficient Repository Cloning
- **GitHub Integration**: Clones GitHub repositories via URL, supporting both `.git` and non-`.git` formats (e.g., `https://github.com/username/repository`).
- **Unique Storage**: Stores cloned repositories in uniquely named folders (e.g., `repoName_uuid`) to avoid conflicts.

### Robust Backend (Flask)
- **RESTful API**: Offers a `POST /clone-repo/` endpoint to accept GitHub URLs, clone repositories, and return cleaned requirements.
- **Input Validation**: Employs Pydantic to validate GitHub URLs, ensuring correct formatting and preventing invalid requests.
- **Asynchronous Cleanup**: Schedules background cleanup of cloned repositories using `asyncio` and `ThreadPoolExecutor` for efficient disk management.
- **Cross-Platform Support**: Manages cleanup on Windows and Unix-like systems, handling open file handles and permissions with `psutil` and `shutil`.
- **Comprehensive Logging**: Logs cloning, dependency generation, and errors to `repo_cloner.log` and `stdout` for debugging and monitoring.

### User-Friendly Frontend (Vite)
- **Modern SPA**: Built with Vite and React, providing a fast, responsive single-page application.
- **Interactive UI**: Enables users to:
  - Input a GitHub repository URL.
  - Submit the URL to trigger cloning and dependency analysis.
  - View the cleaned `requirements.txt` in a formatted display.



## Installation

### Prerequisites
- Python 3.8 or higher
- Git installed and accessible from the command line
- Node.js 18 or higher
- npm or Yarn for frontend package management
- Gemini API key (optional for intelligent dependency analysis)

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
 
4. Create a `.env` file in the `backend` directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   CLONE_BASE_DIR=../cloned_repos
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
 