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
    # Exclude the manifest file itself and the default name if present
    excluded_filenames = {
        os.path.normcase(os.path.basename(output_file)),
        os.path.normcase('manifest.txt')
    }
    
    for filename in os.listdir(source_dir):
        file_path = os.path.join(source_dir, filename)
        
        if os.path.isdir(file_path):
            continue
        
        # Skip files that should not be included in the manifest
        if os.path.normcase(filename) in excluded_filenames:
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
        # Ensure the output directory exists
        output_dir = os.path.dirname(os.path.abspath(output_file))
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
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
                       help='Output manifest filename or path (relative to source_dir). Default: manifest.txt')
    
    args = parser.parse_args()
    
    # Place the manifest inside the source directory when a relative path/filename is provided
    if os.path.isabs(args.output_file):
        output_path = args.output_file
    else:
        output_path = os.path.join(args.source_dir, args.output_file)
    
    print(f"Generating manifest for: {args.source_dir}")
    print(f"Output file: {output_path}")
    print()
    
    success = generate_manifest(args.source_dir, output_path)
    
    if success:
        print("\nManifest generation completed successfully!")
        sys.exit(0)
    else:
        print("\nManifest generation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 