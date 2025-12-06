import os
import subprocess
import shutil
import sys
import time

# Determine project root relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

# Directories containing Python scripts to be flattened into /lib on the device
LIB_SOURCE_DIRS = [
    "libraries"
]

# Other files/folders to sync to root
# (Source Path relative to project root)
STATIC_DIRS = []

ROOT_FILES = [
    "main.py",
]

def run_mpremote(args, ignore_error=False):
    """Run mpremote command."""
    # Use 'python -m mpremote' to avoid PATH issues on Windows
    cmd = [sys.executable, "-m", "mpremote"] + args
    # print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        if not ignore_error:
            raise e
        print(f"Ignored error: {e}")

def deploy():
    # Change to project root to make relative paths work
    os.chdir(PROJECT_ROOT)
    
    print(f"\nDeploying from {PROJECT_ROOT}...")

    # 1. Create /lib directory on device
    print("Ensuring /lib exists...")
    run_mpremote(["mkdir", "lib"], ignore_error=True)

    # 2. Copy Python scripts to /lib (Flattening)
    print("Deploying libraries to /lib...")
    copied_files = set()
    
    for source_dir in LIB_SOURCE_DIRS:
        if not os.path.exists(source_dir):
            print(f"Warning: Source directory '{source_dir}' not found.")
            continue
            
        print(f"  Processing {source_dir}...")
        for root, _, files in os.walk(source_dir):
            if "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    src_path = os.path.join(root, file)
                    # Check for duplicates
                    if file in copied_files:
                        print(f"    WARNING: Overwriting {file} (found in multiple locations)")
                    
                    dest_path = f":lib/{file}"
                    print(f"    {src_path} -> {dest_path}")
                    run_mpremote(["cp", src_path, dest_path])
                    copied_files.add(file)

    # 3. Copy static directories
    if STATIC_DIRS:
        print("\nDeploying static directories...")
        for src in STATIC_DIRS:
            if os.path.exists(src):
                print(f"  Copying {src}...")
                # cp -r source : copies source directory into root
                run_mpremote(["cp", "-r", src, ":"])
            else:
                print(f"  Warning: Directory '{src}' not found.")

    # 4. Copy root files
    print("\nDeploying root files...")
    for f in ROOT_FILES:
        if os.path.exists(f):
            print(f"  Copying {f}...")
            run_mpremote(["cp", f, ":"])
        else:
            # Don't warn for secret_config if it doesn't exist (might be on device only)
            if f != "secret_config.py":
                print(f"  Warning: File '{f}' not found.")

    print("\nDeployment complete. Soft resetting...")
    run_mpremote(["reset"], ignore_error=True)

    print("Waiting for device to reconnect...")
    time.sleep(2)

    print("\nMonitoring device output... (Ctrl+C to exit)")
    try:
        run_mpremote(["repl"])
    except (subprocess.CalledProcessError, KeyboardInterrupt):
        # mpremote repl exits with an error on Ctrl+C, which is normal.
        print("\nExited monitor.")


if __name__ == "__main__":
    try:
        deploy()
    except KeyboardInterrupt:
        print("\nDeployment cancelled.")
    except Exception as e:
        print(f"\nDeployment failed: {e}")
