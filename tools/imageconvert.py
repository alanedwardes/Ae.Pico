import argparse
import struct
from PIL import Image
import sys
import os

def convert_image(input_path, output_path, colors=8):
    img = Image.open(input_path)
    img = img.convert('RGBA')
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    img = img.convert('P', palette=Image.ADAPTIVE, colors=colors)
    palette = img.getpalette()
    used_palette_indices = sorted(set(img.getdata()))
    palette_size = len(used_palette_indices)
    palette_rgb = [tuple(palette[i*3:i*3+3]) for i in used_palette_indices]
    pixels = list(img.getdata())
    width, height = img.size
    with open(output_path, 'wb') as f:
        f.write(struct.pack('<HHH', palette_size, width, height))
        for color in palette_rgb:
            f.write(bytes(color))
        index_map = {orig: new for new, orig in enumerate(used_palette_indices)}
        remapped_pixels = bytes([index_map[p] for p in pixels])
        f.write(remapped_pixels)
    print(f"Converted '{input_path}' to '{output_path}' ({width}x{height}, {palette_size} colors)")

def info_image(bin_path):
    with open(bin_path, 'rb') as f:
        palette_size, width, height = struct.unpack('<HHH', f.read(6))
        palette = [tuple(f.read(3)) for _ in range(palette_size)]
        pixels = list(f.read(width * height))
    print(f"Palette size: {palette_size}")
    print(f"Image size: {width}x{height}")
    print("Palette (index: RGB):")
    for idx, color in enumerate(palette):
        print(f"{idx}: {color}")
    print("First 10 pixel indices:", pixels[:10])

def main():
    parser = argparse.ArgumentParser(description="Image palette converter utility")
    subparsers = parser.add_subparsers(dest='command', required=True)

    convert_parser = subparsers.add_parser('convert', help='Convert PNG to binary format')
    convert_parser.add_argument('input', help='Input PNG file')
    convert_parser.add_argument('output', help='Output binary file')
    convert_parser.add_argument('--colors', type=int, default=8, help='Number of colors in palette (default: 8)')

    info_parser = subparsers.add_parser('info', help='Show info about binary image file')
    info_parser.add_argument('input', help='Input binary file')

    args = parser.parse_args()

    if args.command == 'convert':
        convert_image(args.input, args.output, args.colors)
    elif args.command == 'info':
        info_image(args.input)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()