import argparse
import struct
from PIL import Image
import sys
import os
import glob

def convert_image(input_path, output_path, fmt='rgb24'):
    img = Image.open(input_path).convert('RGBA')
    # Find bounding box of non-transparent pixels BEFORE compositing
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    # Composite over black background
    bg = Image.new('RGBA', img.size, (0, 0, 0, 255))
    img = Image.alpha_composite(bg, img)
    width, height = img.size

    # Get RGB pixels (no alpha)
    pixels = list(img.convert('RGB').getdata())

    with open(output_path, 'wb') as f:
        f.write(struct.pack('<HH', width, height))

        if fmt == 'rgb8':
            # 8-bit RGB332: 3 bits red, 3 bits green, 2 bits blue
            for r, g, b in pixels:
                rgb8 = ((r & 0xE0) | ((g & 0xE0) >> 3) | (b >> 6))
                f.write(bytes([rgb8]))
        elif fmt == 'rgb565be':
            # 16-bit RGB565, big-endian
            for r, g, b in pixels:
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                f.write(struct.pack('>H', rgb565))
        elif fmt == 'rgb24':
            # 24-bit RGB, 8 bits per channel
            for r, g, b in pixels:
                f.write(bytes([r, g, b]))
        elif fmt == 'rgb32':
            # 32-bit RGB, 8 bits per channel (RGBA with alpha=255)
            for r, g, b in pixels:
                f.write(struct.pack('<BBBB', r, g, b, 255))
        else:
            print(f"Unknown format: {fmt}")
            sys.exit(1)

    print(f"Converted '{input_path}' to '{output_path}' ({width}x{height}, format: {fmt})")

def info_image(bin_path):
    with open(bin_path, 'rb') as f:
        width, height = struct.unpack('<HH', f.read(4))
        print(f"Image size: {width}x{height}")
        # Not printing pixel data, as format is now variable

def convert_images(input_path, output_dir, fmt='rgb24'):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    image_files = []
    if os.path.isdir(input_path):
        image_files = glob.glob(os.path.join(input_path, '*.png'))
    else:
        image_files = [input_path]
    for img_file in image_files:
        base = os.path.splitext(os.path.basename(img_file))[0]
        out_file = os.path.join(output_dir, base + '.bin')
        convert_image(img_file, out_file, fmt)

def main():
    parser = argparse.ArgumentParser(description="Image format converter utility")
    subparsers = parser.add_subparsers(dest='command', required=True)

    convert_parser = subparsers.add_parser('convert', help='Convert PNG(s) to raw format')
    convert_parser.add_argument('input', help='Input PNG file or directory')
    convert_parser.add_argument('output', help='Output binary file or directory')
    convert_parser.add_argument('--format', choices=['rgb8', 'rgb565be', 'rgb24', 'rgb32'], default='rgb24',
                               help='Output format: rgb8, rgb565be, rgb24, or rgb32 (default: rgb24)')

    info_parser = subparsers.add_parser('info', help='Show info about binary image file')
    info_parser.add_argument('input', help='Input binary file')

    args = parser.parse_args()

    if args.command == 'convert':
        if os.path.isdir(args.input):
            convert_images(args.input, args.output, args.format)
        else:
            convert_image(args.input, args.output, args.format)
    elif args.command == 'info':
        info_image(args.input)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()