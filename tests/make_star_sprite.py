from PIL import Image, ImageDraw, ImageFilter

size = 64
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
center = size // 2
radius = size // 2 - 2

# Draw a centered white circle with a soft edge
for r in range(radius, 0, -1):
    alpha = int(255 * (1 - r / radius) ** 2)
    draw.ellipse(
        (center - r, center - r, center + r, center + r),
        fill=(255, 255, 255, alpha)
    )

img = img.filter(ImageFilter.GaussianBlur(radius=2))
img.save("models/star_sprite.png")
print("Saved centered star_sprite.png")