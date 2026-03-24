import os
import re
import shutil
import pandas as pd
from git import Repo
import uuid

def clone_repo(repo_url):
    folder_name = "repo_" + str(uuid.uuid4())[:8]

    print("📥 Cloning repository...")
    Repo.clone_from(repo_url, folder_name)

    print(f"✅ Repository cloned into: {folder_name}")
    return folder_name

def get_all_files(folder):
    file_paths = []

    skip_folders = ['node_modules', '.git', 'vendor', '__pycache__']

    for root, dirs, files in os.walk(folder):

        # Skip heavy folders
        dirs[:] = [d for d in dirs if d not in skip_folders]

        for file in files:
            if file.endswith(('.php', '.js', '.html', '.py')):
                file_paths.append(os.path.join(root, file))

    return file_paths

def get_file_type(file):
    if file.endswith(('.html', '.js', '.jsx')):
        return "Frontend"
    elif file.endswith(('.php', '.py', '.js')):
        return "Backend"
    return "Other"

def is_upload_code(line):
    keywords = [
        'input type="file"',
        "type='file'",
        "$_files",
        "request.files",
        "req.file",
        "multer"
    ]
    return any(keyword in line.lower() for keyword in keywords)

def detect_validation(context):
    validation_keywords = [
        "pdf", "jpg", "jpeg", "png",
        "filetype", "mimetype", "allowed",
        "accept", "content-type"
    ]

    found = any(keyword in context.lower() for keyword in validation_keywords)

    types = re.findall(r"(pdf|jpg|jpeg|png)", context.lower())
    allowed_types = ",".join(set(types))

    return found, allowed_types

results = []

def scan_files(files):
    for file in files:
        file_type = get_file_type(file)

        try:
            with open(file, "r", errors="ignore") as f:
                lines = f.readlines()

                for i, line in enumerate(lines, start=1):

                    if is_upload_code(line):

                        validation = "No"
                        allowed_types = ""

                        # Context scan (previous + next lines)
                        context = "".join(lines[max(0, i-3):i+3])

                        found, types = detect_validation(context)

                        if found:
                            validation = "Yes"
                            allowed_types = types

                        # Severity Logic
                        if validation == "No":
                            severity = "High"
                        elif file_type == "Frontend":
                            severity = "Medium"
                        else:
                            severity = "Low"

                        results.append({
                            "File Name": os.path.basename(file),
                            "Path": file,
                            "Type": file_type,
                            "Validation": validation,
                            "Allowed Types": allowed_types,
                            "Severity": severity,
                            "Line Number": i,
                            "Code Snippet": line.strip()
                        })

        except Exception as e:
            print(f"⚠️ Error reading {file}: {e}")

def generate_report():
    if not results:
        print("⚠️ No upload-related code found!")
        return

    df = pd.DataFrame(results)

    if not os.path.exists("output"):
        os.makedirs("output")

    output_path = "output/report.xlsx"
    df.to_excel(output_path, index=False)

    print(f"📊 Report generated successfully: {output_path}")

if __name__ == "__main__":
    repo_url = input("🔗 Enter GitHub Repo URL: ")

    repo_folder = clone_repo(repo_url)

    print("🔍 Scanning files...")
    files = get_all_files(repo_folder)

    scan_files(files)
    generate_report()

    print("🚀 Scan completed!")