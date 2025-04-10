# images.py

from PIL import Image, ImageOps, ImageEnhance
import os
import shutil

def optimize_images(base_dir, output_dir):
    print("Optimizing images...")
    # This function can be extended if needed.

def dither_image(input_path, output_path):
    # Open the image file
    with Image.open(input_path) as img:
        # Convert the image to grayscale
        img = img.convert('L')

        # Apply dithering
        img = img.convert('1')  # Convert to black and white with dithering

        # Save the optimized image
        img.save(output_path, optimize=True, format='PNG')  # Save as PNG to support black and white

def copy_original_image(input_path, output_path):
    # Copy the original image to the output directory
    shutil.copy2(input_path, output_path)
