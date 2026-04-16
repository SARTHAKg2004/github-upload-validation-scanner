import os
import requests
import pandas as pd
import json
import shutil
import sys
import subprocess
import time
import stat
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ==============================
# 🚀 GPU SETUP (ADDED)
# ==============================
try:
    import torch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("🔥 GPU Device:", device)
except:
    device = "cpu"
    print("🚀 Using Ollama GPU acceleration")

# ==============================
# CONFIGURATION
# ==============================
OLLAMA_URL = "http://localhost:11434/api/generate"

FAST_MODEL = "phi3"
DEEP_MODEL = "phi3"

SUPPORTED_EXTENSIONS = [".py", ".js", ".java", ".cpp", ".c", ".ts"]
IGNORE_FOLDERS = ["node_modules", "venv", ".git", "__pycache__"]

MAX_LINES = 100
MAX_WORKERS = 15

# ==============================
# 🚀 GPU REQUEST SESSION (ADDED)
# ==============================
session = requests.Session()

# ==============================
# CLONE REPO
# ==============================
def download_repo(repo_url):
    try:
        folder_name = f"repo_{int(time.time())}"

        print("\n⬇️ Cloning repository...")

        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, folder_name],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("❌ Git clone failed:")
            print(result.stderr)
            return None

        print("✅ Repository cloned successfully\n")
        return folder_name

    except Exception as e:
        print("❌ Error cloning repo:", e)
        return None

# ==============================
# SCAN FILES
# ==============================
def scan_repository(repo_path):
    files_data = []

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_FOLDERS]

        for file in files:
            if any(file.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                filepath = os.path.join(root, file)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        code = "".join(f.readlines()[:MAX_LINES])

                    files_data.append({
                        "file": filepath,
                        "code": code
                    })

                except:
                    continue

    return files_data

# ==============================
# FAST SCAN (PHI)
# ==============================
def fast_scan_phi(code, filename):
    prompt = f"""
Check if this code has issues.

Reply ONLY:
YES → if issues exist
NO → if clean

Code:
{code}
"""

    try:
        response = session.post(
            OLLAMA_URL,
            json={
                "model": FAST_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_gpu": 1  # 🚀 FORCE GPU
                }
            },
            timeout=60
        )

        return response.json().get("response", "").strip().upper()

    except:
        return "YES"

# ==============================
# DEEP ANALYSIS (QWEN)
# ==============================
def analyze_with_llm(code, filename):
    prompt = f"""
You are an expert code reviewer.

Return STRICT JSON:

[
  {{
    "file": "{filename}",
    "issue_type": "",
    "description": "",
    "line": "",
    "severity": "High/Medium/Low",
    "suggestion": ""
  }}
]

Rules:
- Detect bugs, bad practices, security issues
- If no issues, return []
- Output ONLY JSON

Code:
{code}
"""

    try:
        response = session.post(
            OLLAMA_URL,
            json={
                "model": DEEP_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_gpu": 1  # 🚀 FORCE GPU
                }
            },
            timeout=120
        )

        return response.json().get("response", "[]")

    except Exception as e:
        print(f"❌ LLM Error: {e}")
        return "[]"

# ==============================
# PARSE OUTPUT
# ==============================
def parse_llm_output(output):
    try:
        return json.loads(output)
    except:
        return []

# ==============================
# PARALLEL PROCESSING
# ==============================
def process_files_parallel(files):
    def process(file):
        print(f"⚡ Fast scan: {file['file']}")
        fast_result = fast_scan_phi(file["code"], file["file"])

        if fast_result == "NO" or fast_result == "SKIP":
            return []

        print(f"🧠 Deep scan: {file['file']}")
        output = analyze_with_llm(file["code"], file["file"])
        return parse_llm_output(output)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(process, files))

    return results

# ==============================
# OPEN FILE (CROSS PLATFORM)
# ==============================
def open_file(filepath):
    try:
        if sys.platform.startswith('win'):
            os.startfile(filepath)
        elif sys.platform.startswith('darwin'):
            subprocess.call(['open', filepath])
        else:
            subprocess.call(['xdg-open', filepath])
        print("📂 Opening report...")
    except:
        print("👉 Open manually:", filepath)

# ==============================
# GENERATE EXCEL
# ==============================
def generate_excel(results):
    rows = []

    for result in results:
        if isinstance(result, list):
            rows.extend(result)

    if not rows:
        print("✅ No issues found.")
        return

    df = pd.DataFrame(rows)

    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.abspath(filename)

    df.to_excel(filepath, index=False)

    print("\n📊 REPORT GENERATED")
    print("📁 File:", filename)
    print("📍 Path:", filepath)

    print("\nOptions:")
    print("1. Open report")
    print("2. Move to Downloads")
    print("3. Exit")

    choice = input("Choice: ")

    if choice == "1":
        open_file(filepath)

    elif choice == "2":
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        new_path = os.path.join(downloads, filename)

        shutil.move(filepath, new_path)
        print("📥 Saved to Downloads:", new_path)
        open_file(new_path)

# ==============================
# SAFE CLEANUP (FIXED)
# ==============================
def remove_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def cleanup(folder):
    if not os.path.exists(folder):
        return

    print("\n🧹 Cleaning up temporary files...")

    for i in range(3):
        try:
            shutil.rmtree(folder, onerror=remove_readonly)
            print("✅ Cleanup successful")
            return
        except Exception:
            print(f"⚠️ Retry cleanup ({i+1}/3)...")
            time.sleep(2)

    print("⚠️ Could not fully delete repo (safe to ignore)")

# ==============================
# MAIN
# ==============================
def main():
    repo_url = input("Enter GitHub Repo URL: ").strip()

    repo_path = download_repo(repo_url)
    if not repo_path:
        return

    print("🔍 Scanning files...")
    files = scan_repository(repo_path)

    print(f"📂 Files found: {len(files)}\n")

    print("⚡ Running hybrid AI scan...\n")
    results = process_files_parallel(files)

    print("\n📊 Generating report...")
    generate_excel(results)

    cleanup(repo_path)

    print("\n🎉 Done!")

# ==============================
if __name__ == "__main__":
    main()