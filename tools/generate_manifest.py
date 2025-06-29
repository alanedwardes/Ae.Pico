import os
import hashlib
import sys
import argparse

def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    
    with open(file_path, 'rb') as file:
        while True:
            chunk = file.read(8192)
            if not chunk:
                break
            sha256_hash.update(chunk)
    
    return sha256_hash.hexdigest()

def generate_manifest(source_dir, output_file):   
    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist")
        return False
    
    manifest_entries = []
    
    for filename in os.listdir(source_dir):
        file_path = os.path.join(source_dir, filename)
        
        if os.path.isdir(file_path):
            continue
        
        try:
            file_hash = calculate_sha256(file_path)
            manifest_entries.append((filename, file_hash))
            print(f"Processed: {filename} -> {file_hash}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            return False
    
    manifest_entries.sort(key=lambda x: x[0])
    
    try:
        with open(output_file, 'w') as f:
            for filename, file_hash in manifest_entries:
                f.write(f"{filename} {file_hash}\n")
        
        print(f"\nManifest file created: {output_file}")
        print(f"Total files included: {len(manifest_entries)}")
        return True
        
    except Exception as e:
        print(f"Error writing manifest file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate SHA256 manifest for files in a directory")
    parser.add_argument('source_dir', help='Source directory to scan for files')
    parser.add_argument('output_file', nargs='?', default='manifest.txt', 
                       help='Output manifest file (default: manifest.txt)')
    
    args = parser.parse_args()
    
    print(f"Generating manifest for: {args.source_dir}")
    print(f"Output file: {args.output_file}")
    print()
    
    success = generate_manifest(args.source_dir, args.output_file)
    
    if success:
        print("\nManifest generation completed successfully!")
        sys.exit(0)
    else:
        print("\nManifest generation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 