import mimetypes
import os.path
import posixpath
import random
from pathlib import Path

import magic
from django.conf import settings
from django.http import HttpResponse
from django.utils._os import safe_join
from PIL import Image, ImageDraw, ImageFile, ImageFont, ImageSequence


def serve(path, document_root=None, file_name=None, force_encoding=None):
    path = posixpath.normpath(path).lstrip('/')
    fullpath = Path(safe_join(document_root, path))
    if fullpath.is_dir():
        return {
            'status': 'failed',
            'code': 'InvalidFilePath',
            'error': 'Directory indexes are not allowed here.'
        }
    if not fullpath.exists():
        return {
            'status': 'failed',
            'code': 'NotFound',
            'error': f'{path} does not exist'
        }

    content_type, encoding = mimetypes.guess_type(str(fullpath))
    if force_encoding:
        encoding = force_encoding

    mime_type = magic.from_file(str(fullpath), mime=True)
    with open(fullpath, 'rb') as image_file:
        data = image_file.read()
    if mime_type == 'image/gif':
        response = HttpResponse(data, content_type='image/gif')
    elif mime_type.startswith('image/'):
        response = HttpResponse(data, content_type='image/jpeg')
    elif (
        mime_type == 'application/csv' or mime_type == 'text/csv' or mime_type == 'text/plain'
    ) and content_type == 'text/csv':
        response = HttpResponse(data, content_type='text/csv')
    else:
        return {
            'status': 'failed',
            'code': 'NotFound',
            'error': f'{path} does not exist'
        }
    if encoding:
        response['Content-Encoding'] = encoding

    if file_name:
        response['Content-Disposition'] = 'attachment; filename={}'.format(file_name)

    return response


def watermark_gif(src_file, dst_path):
    photo = Image.open(src_file)
    exif_info = photo.info.get('exif', b'')
    photo_width, photo_height = photo.size

    watermark_path = os.path.join(settings.BASE_DIR, 'assets', 'images', 'nobitex_watermark_5.png')
    water_im = Image.open(watermark_path)
    water_im_width, water_im_height = water_im.size
    if water_im_width > photo_width // 2:
        water_im = water_im.resize(size=(water_im_width // 2, water_im_height // 2))
        water_im_width, water_im_height = water_im.size

    x = (photo_width // 2) - (water_im_width // 2)
    y = (photo_height // 2) - (water_im_height // 2)
    center_position = (x, y)

    frames = []
    for frame in ImageSequence.Iterator(photo):
        frame = frame.copy()
        frame.paste(water_im, center_position, water_im)
        frames.append(frame)

    frames[0].save(dst_path, format='Gif', exif=exif_info, append_images=frames[1:], save_all=True, duration=200,
                   loop=0)


def watermark_image(src_file, dst_path):
    from pillow_heif import register_heif_opener
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    register_heif_opener()
    photo = Image.open(src_file).convert('RGB')
    exif_info = photo.info.get('exif', b'')

    # convert photo to RGB
    draw = ImageDraw.Draw(photo, 'RGB')

    # photo width and height
    width, height = photo.size

    # secret hidden Squares
    sq_dimension_scale = 40
    sq_width = width // sq_dimension_scale

    # secret numbers
    # font, more information: https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
    font_path = os.path.join(settings.BASE_DIR, 'assets', 'fonts', 'FreeMono.ttf')
    font = ImageFont.truetype(font_path, width // 65, encoding='unic')

    max_range = 10
    min_range = 1
    fill_color = (255, 255, 255)  # white
    secret_top = random.choice(range(min_range, max_range + 1))
    secret_right = random.choice(range(min_range, max_range + 1))
    secret_bottom = random.choice(range(min_range, max_range + 1))
    secret_left = random.choice(range(min_range, max_range + 1))

    # put secret numbers in squares
    draw.text((sq_width // 2 - sq_width // 5, sq_width // 2 - sq_width // 5), str(secret_right),
              fill=fill_color, font=font)
    draw.text((sq_width // 2 - sq_width // 5, (height - sq_width // 2) - sq_width // 5), str(secret_bottom),
              fill=fill_color, font=font)
    draw.text(((width - sq_width // 2) - sq_width // 5, (height - sq_width // 2) - sq_width // 5), str(secret_left),
              fill=fill_color, font=font)
    draw.text(((width - sq_width // 2) - sq_width // 5, sq_width // 2 - sq_width // 5), str(secret_top),
              fill=fill_color, font=font)

    # watermark image
    watermark_path = os.path.join(settings.BASE_DIR, 'assets', 'images', 'nobitex_watermark_5.png')
    watermark = Image.open(watermark_path)
    watermark_w, watermark_h = watermark.size

    # watermark secret position
    watermark_x_center = width // 2 - watermark_w // 2
    watermark_y_center = height // 2 - watermark_h // 2
    min_secret = min(secret_top, secret_right, secret_bottom, secret_left)

    watermark_x, watermark_y = watermark_x_center, watermark_y_center

    if min_secret == secret_top:
        watermark_x = width - watermark_w - int(((max_range - min_secret) / max_range) * watermark_w)
        watermark_y = watermark_y_center - int((min_secret / max_range) * watermark_y_center)

    elif min_secret == secret_right:
        watermark_x = watermark_w - int((min_secret / max_range) * watermark_w)
        watermark_y = watermark_y_center - int((min_secret / max_range) * watermark_y_center)

    elif min_secret == secret_bottom:
        watermark_x = watermark_w - int((min_secret / max_range) * watermark_w)
        watermark_y = watermark_y_center + int((min_secret / max_range) * watermark_y_center)

    elif min_secret == secret_left:
        watermark_x = width - watermark_w - int(((max_range - min_secret) / max_range) * watermark_w)
        watermark_y = watermark_y_center + int((min_secret / max_range) * watermark_y_center)

    photo.paste(watermark, (watermark_x, watermark_y), watermark)
    photo.save(dst_path, format='jpeg', exif=exif_info, optimize=True, quality=85)
