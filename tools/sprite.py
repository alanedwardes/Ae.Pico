import os
import sys
import csv
from PIL import Image

def trim_transparency(img):
    bbox = img.getbbox()
    if bbox:
        return img.crop(bbox), bbox
    return img, (0, 0, img.width, img.height)

def create_sprite(image_paths, output_image, output_csv):
    images = []
    names = []
    trims = []
    for path in image_paths:
        img = Image.open(path).convert("RGBA")
        trimmed, bbox = trim_transparency(img)
        images.append(trimmed)
        base_name = os.path.splitext(os.path.basename(path))[0]
        names.append(base_name)
        trims.append(bbox)

    # Simple packing: vertical strip
    max_width = max(img.width for img in images)
    total_height = sum(img.height for img in images)

    sprite = Image.new("RGBA", (max_width, total_height), (0, 0, 0, 0))
    rows = []
    y = 0
    for name, img, bbox in zip(names, images, trims):
        sprite.paste(img, (0, y))
        rows.append([name, 0, y, img.width, img.height])
        y += img.height

    sprite.save(output_image)
    with open(output_csv, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "x", "y", "width", "height"])
        writer.writerows(rows)

if __name__ == "__main__":
    # Usage: python sprite.py [img1.png img2.png ... | folder] output.png output.csv
    if len(sys.argv) < 4:
        print("Usage: python sprite.py [img1.png img2.png ... | folder] output.png output.csv")
        sys.exit(1)
    *inputs, output_image, output_csv = sys.argv[1:]

    # If a single folder is provided, use all PNGs in it
    if len(inputs) == 1 and os.path.isdir(inputs[0]):
        folder = inputs[0]
        image_paths = [
            os.path.join(folder, f)
            for f in sorted(os.listdir(folder))
            if f.lower().endswith('.png')
        ]
        if not image_paths:
            print(f"No PNG images found in folder: {folder}")
            sys.exit(1)
    else:
        image_paths = inputs

    create_sprite(image_paths, output_image, output_csv)