import argparse
import struct
import sys
import os
import glob

def convert_image(input_path, output_path, fmt='rgb24'):
    from PIL import Image
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
        elif fmt == 'gs8':
            # 8-bit grayscale (luma ~ Rec.601)
            for r, g, b in pixels:
                y = int(0.299 * r + 0.587 * g + 0.114 * b)
                f.write(bytes([y]))
        elif fmt == 'rgb565be':
            # 16-bit RGB565, big-endian
            for r, g, b in pixels:
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                f.write(struct.pack('>H', rgb565))
        elif fmt == 'rgb565':
            # 16-bit RGB565, little-endian (default)
            for r, g, b in pixels:
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                f.write(struct.pack('<H', rgb565))
        elif fmt == 'rgb24':
            # 24-bit RGB, 8 bits per channel
            for r, g, b in pixels:
                f.write(bytes([r, g, b]))
        elif fmt == 'bgra8888':
            # 32-bit BGRA8888, 8 bits per channel (BGRA with alpha=255)
            for r, g, b in pixels:
                f.write(struct.pack('<BBBB', b, g, r, 255))
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

def _expand_5_to_8(v):
    return (v << 3) | (v >> 2)

def _expand_6_to_8(v):
    return (v << 2) | (v >> 4)

def _decode_pixels(data, width, height, fmt):
    if fmt == 'rgb565be':
        pixels = []
        for i in range(0, len(data), 2):
            val = (data[i] << 8) | data[i + 1]
            r5 = (val >> 11) & 0x1F
            g6 = (val >> 5) & 0x3F
            b5 = val & 0x1F
            r = _expand_5_to_8(r5)
            g = _expand_6_to_8(g6)
            b = _expand_5_to_8(b5)
            pixels.append((r, g, b))
        return pixels
    elif fmt == 'rgb565':
        pixels = []
        for i in range(0, len(data), 2):
            val = data[i] | (data[i + 1] << 8)
            r5 = (val >> 11) & 0x1F
            g6 = (val >> 5) & 0x3F
            b5 = val & 0x1F
            r = _expand_5_to_8(r5)
            g = _expand_6_to_8(g6)
            b = _expand_5_to_8(b5)
            pixels.append((r, g, b))
        return pixels
    elif fmt == 'gs8':
        pixels = []
        for i in range(0, len(data)):
            y = data[i]
            pixels.append((y, y, y))
        return pixels
    elif fmt == 'rgb24':
        pixels = []
        for i in range(0, len(data), 3):
            r = data[i]
            g = data[i + 1]
            b = data[i + 2]
            pixels.append((r, g, b))
        return pixels
    elif fmt == 'bgra8888':
        pixels = []
        for i in range(0, len(data), 4):
            b = data[i]
            g = data[i + 1]
            r = data[i + 2]
            pixels.append((r, g, b))
        return pixels
    else:
        print(f"Unsupported input format: {fmt}")
        sys.exit(1)

def _encode_pixels(pixels, fmt):
    out = bytearray()
    if fmt == 'rgb8':
        for r, g, b in pixels:
            rgb8 = ((r & 0xE0) | ((g & 0xE0) >> 3) | (b >> 6))
            out.append(rgb8)
    elif fmt == 'gs8':
        for r, g, b in pixels:
            y = int(0.299 * r + 0.587 * g + 0.114 * b)
            out.append(y & 0xFF)
    elif fmt == 'rgb565be':
        for r, g, b in pixels:
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out.extend(struct.pack('>H', rgb565))
    elif fmt == 'rgb565':
        for r, g, b in pixels:
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out.extend(struct.pack('<H', rgb565))
    elif fmt == 'rgb24':
        for r, g, b in pixels:
            out.extend((r, g, b))
    elif fmt == 'bgra8888':
        for r, g, b in pixels:
            out.extend(struct.pack('<BBBB', b, g, r, 255))
    else:
        print(f"Unsupported output format: {fmt}")
        sys.exit(1)
    return bytes(out)

def convert_bin_image(input_path, output_path, in_fmt='rgb565be', out_fmt='bgra8888'):
    with open(input_path, 'rb') as f:
        width, height = struct.unpack('<HH', f.read(4))
        data = f.read()
    pixels = _decode_pixels(data, width, height, in_fmt)
    encoded = _encode_pixels(pixels, out_fmt)
    with open(output_path, 'wb') as f:
        f.write(struct.pack('<HH', width, height))
        f.write(encoded)
    print(f"Converted '{input_path}' to '{output_path}' ({width}x{height}, {in_fmt} -> {out_fmt})")

def convert_bin_images(input_path, output_dir, in_fmt='rgb565be', out_fmt='bgra8888'):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    bin_files = []
    if os.path.isdir(input_path):
        bin_files = glob.glob(os.path.join(input_path, '*.bin'))
    else:
        bin_files = [input_path]
    for bin_file in bin_files:
        base = os.path.splitext(os.path.basename(bin_file))[0]
        out_file = os.path.join(output_dir, base + '.bin')
        convert_bin_image(bin_file, out_file, in_fmt, out_fmt)

def main():
    parser = argparse.ArgumentParser(description="Image format converter utility")
    subparsers = parser.add_subparsers(dest='command', required=True)

    convert_parser = subparsers.add_parser('convert', help='Convert image(s) to raw format')
    convert_parser.add_argument('input', help='Input image file or directory')
    convert_parser.add_argument('output', nargs='?', help='Output binary file or directory (default: input name with .bin)')
    convert_parser.add_argument('--format', choices=['rgb8', 'gs8', 'rgb565', 'rgb565be', 'rgb24', 'bgra8888'], default='rgb24',
                               help='Output format: rgb8, rgb565 (LE), rgb565be, rgb24, bgra8888 (default: rgb24)')

    convertbin_parser = subparsers.add_parser('convertbin', help='Convert BIN(s) between raw formats')
    convertbin_parser.add_argument('input', help='Input BIN file or directory')
    convertbin_parser.add_argument('output', nargs='?', help='Output BIN file or directory (default: input name with .bin)')
    convertbin_parser.add_argument('--in-format', choices=['gs8', 'rgb565', 'rgb565be', 'rgb24', 'bgra8888'], default='rgb565',
                                  help='Input pixel format (default: rgb565, little-endian)')
    convertbin_parser.add_argument('--out-format', choices=['rgb8', 'gs8', 'rgb565', 'rgb565be', 'rgb24', 'bgra8888'], default='bgra8888',
                                   help='Output pixel format (default: bgra8888)')

    info_parser = subparsers.add_parser('info', help='Show info about binary image file')
    info_parser.add_argument('input', help='Input binary file')

    args = parser.parse_args()

    if args.command == 'convert':
        if os.path.isdir(args.input):
            output_dir = args.output if args.output else args.input
            convert_images(args.input, output_dir, args.format)
        else:
            default_output = os.path.splitext(args.input)[0] + '.bin'
            output_file = args.output if args.output else default_output
            convert_image(args.input, output_file, args.format)
    elif args.command == 'convertbin':
        if os.path.isdir(args.input):
            output_dir = args.output if args.output else args.input
            convert_bin_images(args.input, output_dir, args.in_format, args.out_format)
        else:
            default_output = os.path.splitext(args.input)[0] + '.bin'
            output_file = args.output if args.output else default_output
            convert_bin_image(args.input, output_file, args.in_format, args.out_format)
    elif args.command == 'info':
        info_image(args.input)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()