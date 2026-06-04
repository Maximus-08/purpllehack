import zipfile
import os

def create_zip():
    exclude_dirs = {'.venv', 'venv', '__pycache__', '.git', '.pytest_cache', '.agents', '.codex'}
    exclude_files = {'submission.zip', '.coverage'}
    exclude_exts = {'.db', '.sqlite', '.pyc', '.pyo', '.pt'}
    
    zip_path = 'submission.zip'
    if os.path.exists(zip_path):
        os.remove(zip_path)
        
    print(f"Creating clean {zip_path} archive...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if file in exclude_files:
                    continue
                if os.path.splitext(file)[1] in exclude_exts:
                    continue
                
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, '.')
                zipf.write(filepath, arcname)
    print("Done. submission.zip successfully created.")

if __name__ == "__main__":
    create_zip()
