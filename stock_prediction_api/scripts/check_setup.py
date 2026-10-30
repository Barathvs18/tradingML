import os
import yaml
import importlib.metadata

def print_result(check_name: str, passed: bool, details: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {check_name}")
    if details:
        print(f"         {details}")

def check_setup():
    print("--- Stock Prediction Platform: Phase 5 Setup Check ---")
    
    # 1. Check data/
    data_dir = os.path.join(os.getcwd(), 'data')
    data_exists = os.path.isdir(data_dir)
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')] if data_exists else []
    print_result("Data directory exists", data_exists)
    print_result("CSV files found in data/", len(csv_files) > 0, f"Found {len(csv_files)} CSV files" if data_exists else "Directory missing")

    # 2. Check models/
    models_dir = os.path.join(os.getcwd(), 'models')
    models_exists = os.path.isdir(models_dir)
    print_result("Models directory exists", models_exists)
    
    # 3. Check manifest
    manifest_path = os.path.join(models_dir, 'manifest.yaml')
    manifest_exists = os.path.isfile(manifest_path)
    print_result("Manifest file exists", manifest_exists, "models/manifest.yaml")
    
    if manifest_exists:
        try:
            with open(manifest_path, 'r') as f:
                manifest = yaml.safe_load(f)
            
            algos = manifest.get('algorithms', {})
            all_files_exist = True
            missing_files = []
            
            for key, config in algos.items():
                model_file = config.get('file')
                if model_file and not os.path.isfile(os.path.join(models_dir, model_file)):
                    all_files_exist = False
                    missing_files.append(model_file)
                    
                scaler_file = config.get('scaler_file')
                if scaler_file and not os.path.isfile(os.path.join(models_dir, scaler_file)):
                    all_files_exist = False
                    missing_files.append(scaler_file)
            
            print_result("Manifest files exist", all_files_exist, f"Missing: {missing_files}" if not all_files_exist else "All referenced model/scaler files found.")
        except Exception as e:
            print_result("Manifest files exist", False, f"Failed to parse manifest: {e}")

    # 4. Check .gitignore
    gitignore_path = os.path.join(os.getcwd(), '.gitignore')
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, 'r') as f:
            content = f.read()
            data_ignored = 'data/' in content or 'data' in content
            models_ignored = 'models/' in content or 'models' in content
            print_result(".gitignore excludes data/ and models/", data_ignored and models_ignored)
    else:
        print_result(".gitignore excludes data/ and models/", False, ".gitignore file not found")

    # 5. Check requirements.txt library versions
    req_path = os.path.join(os.getcwd(), 'requirements.txt')
    if os.path.isfile(req_path):
        with open(req_path, 'r') as f:
            reqs = f.readlines()
            
        mismatches = []
        for req in reqs:
            req = req.strip()
            if '==' in req:
                lib, expected_version = req.split('==')
                lib = lib.strip()
                expected_version = expected_version.strip()
                try:
                    # Replace common package names for importlib
                    dist_name = lib
                    if lib.lower() == 'scikit-learn': dist_name = 'scikit_learn'
                    elif lib.lower() == 'opencv-python': dist_name = 'cv2'
                    
                    actual_version = importlib.metadata.version(dist_name)
                    if actual_version != expected_version:
                        mismatches.append(f"{lib}: expected {expected_version}, got {actual_version}")
                except importlib.metadata.PackageNotFoundError:
                    mismatches.append(f"{lib}: not installed")
        
        print_result("Library versions match requirements.txt", len(mismatches) == 0, ", ".join(mismatches) if mismatches else "All pinned versions match")
    else:
        print_result("Library versions match requirements.txt", False, "requirements.txt not found")
        
    print("------------------------------------------------------")

if __name__ == "__main__":
    check_setup()
