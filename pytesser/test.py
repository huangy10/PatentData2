import os
from PIL import Image

import pytesser


def preprocess(image_path):
    with Image.open(image_path) as im:
        i = 0
        mypalette = im.getpalette()
        home = os.path.abspath(os.path.dirname(image_path))
        try:
            while 1:
                im.putpalette(mypalette)
                new_im = Image.new("RGBA", im.size)
                new_im.paste(im)
                filename = 'foo' + str(i) + '.png'
                new_im.save(os.path.join(home, filename))

                i += 1
                im.seek(im.tell() + 1)
        except EOFError:
            pass

predefine_color = [
    153 * 65536 + 43 * 256 + 51,
]


def color_map(color):
    r, g, b = color
    # if r == 0 or g == 0 or b == 0:
    #     return 0
    # elif r * 65536 + g * 255 + b in predefine_color:
    #     return 0
    # else:
    #     return 255
    if r + g + b < 10:
        return 0
    temp = r * 0.299 + g * 0.587 + 0.114 * b
    temp = abs(r - temp) + abs(g - temp) + abs(b - temp)
    if temp > 110:
        return 0
    else:
        return 255


def gif_to_png(im):
    mypalette = im.getpalette()
    try:
        while 1:
            im.putpalette(mypalette)
            new_im = Image.new("RGB", im.size)
            new_im.paste(im)
            return new_im
    except EOFError:
        return None


def filter_image(im):
    im = gif_to_png(im)
    new_im = Image.new("L", im.size)
    pix = new_im.load()
    old_pix = im.load()
    w, h = im.size
    for col in range(w):
        for row in range(h):
            if row == 0 or col == 0 or row == h - 1 or col == w - 1:
                pix[col, row] = 255
            else:
                pix[col, row] = color_map(old_pix[col, row])
    return new_im


def prepare_image(path):
    with Image.open(path) as im:
        a = filter_image(im)
        return a


def x_map(im):
    pix = im.load()
    w, h = im.size
    map_x = []
    for col in range(w):
        col_p = map(lambda x: 255 - pix[col, x], range(h))
        if sum(col_p) == 0:
            map_x.append(0)
        else:
            map_x.append(1)
    res = []
    col = 0
    while col < w:
        if map_x[col] == 0:
            col += 1
            continue
        count = 0
        temp_res = []
        for i in range(col, w):
            if map_x[i] == 1:
                count += 1
                temp_res.append(i)
            else:
                break
        if count > 5:
            res.append(temp_res)
        col += count
    return res


def divide_image(im):
    res = x_map(im)
    w, h = im.size
    old_pix = im.load()
    if len(res) != 4:
        return None
    result = []
    for xs in res:
        new_im = Image.new("L", (len(xs), h))
        pix = new_im.load()
        for i, col in enumerate(xs):
            for row in range(h):
                pix[i, row] = old_pix[col, row]

        result.append(new_im)
    return result


def rotate_image(im):
    pass

