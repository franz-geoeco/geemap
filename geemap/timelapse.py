"""Module for creating timelapse from Earth Engine data."""

# *******************************************************************************#
# This module contains extra features of the geemap package.                     #
# The geemap community will maintain the extra features.                         #
# *******************************************************************************#

import datetime
import glob
import io
import os
import shutil

import ee

from .common import *
from typing import Union, List

try:
    from PIL import Image
except:
    pass


def add_overlay(
    collection: ee.ImageCollection,
    overlay_data: Union[str, ee.Geometry, ee.FeatureCollection],
    color: str = "black",
    width: int = 1,
    opacity: float = 1.0,
    region: Union[ee.Geometry, ee.FeatureCollection] = None,
) -> ee.ImageCollection:
    """Adds an overlay to an image collection.

    Args:
        collection (ee.ImageCollection): The image collection to add the overlay to.
        overlay_data (str | ee.Geometry | ee.FeatureCollection): The overlay data to add to the image collection. It can be an HTTP URL to a GeoJSON file.
        color (str, optional): The color of the overlay. Defaults to 'black'.
        width (int, optional): The width of the overlay. Defaults to 1.
        opacity (float, optional): The opacity of the overlay. Defaults to 1.0.
        region (ee.Geometry | ee.FeatureCollection, optional): The region of interest to add the overlay to. Defaults to None.

    Returns:
        ee.ImageCollection: An ImageCollection with the overlay added.
    """

    # Some common administrative boundaries.
    public_assets = ["continents", "countries", "us_states", "china"]

    if not isinstance(collection, ee.ImageCollection):
        raise Exception("The collection must be an ee.ImageCollection.")

    if not isinstance(overlay_data, ee.FeatureCollection):
        if isinstance(overlay_data, str):
            try:
                if overlay_data.lower() in public_assets:
                    overlay_data = ee.FeatureCollection(
                        f"users/giswqs/public/{overlay_data.lower()}"
                    )
                elif overlay_data.startswith("http") and overlay_data.endswith(
                    ".geojson"
                ):
                    overlay_data = geojson_to_ee(overlay_data)
                else:
                    overlay_data = ee.FeatureCollection(overlay_data)

            except Exception as e:
                print(
                    "The overlay_data must be a valid ee.FeatureCollection, a valid ee.FeatureCollection asset id, or http url to a geojson file."
                )
                raise Exception(e)
        elif isinstance(overlay_data, ee.Feature):
            overlay_data = ee.FeatureCollection([overlay_data])
        elif isinstance(overlay_data, ee.Geometry):
            overlay_data = ee.FeatureCollection([ee.Feature(overlay_data)])
        else:
            raise Exception(
                "The overlay_data must be a valid ee.FeatureCollection or a valid ee.FeatureCollection asset id."
            )

    try:
        if region is not None:
            overlay_data = overlay_data.filterBounds(region)

        empty = ee.Image().byte()
        image = empty.paint(
            **{
                "featureCollection": overlay_data,
                "color": 1,
                "width": width,
            }
        ).visualize(**{"palette": check_color(color), "opacity": opacity})
        blend_col = collection.map(
            lambda img: img.blend(image).set(
                "system:time_start", img.get("system:time_start")
            )
        )
        return blend_col
    except Exception as e:
        print("Error in add_overlay:")
        raise Exception(e)


def make_gif(
    images: Union[List[str], str],
    out_gif: str,
    ext: str = "jpg",
    fps: int = 10,
    loop: int = 0,
    mp4: bool = False,
    clean_up: bool = False,
) -> None:
    """Creates a gif from a list of images.

    Args:
        images (list | str): The list of images or input directory to create the gif from.
        out_gif (str): File path to the output gif.
        ext (str, optional): The extension of the images. Defaults to 'jpg'.
        fps (int, optional): The frames per second of the gif. Defaults to 10.
        loop (int, optional): The number of times to loop the gif. Defaults to 0.
        mp4 (bool, optional): Whether to convert the gif to mp4. Defaults to False.

    """
    if isinstance(images, str) and os.path.isdir(images):
        images = list(glob.glob(os.path.join(images, f"*.{ext}")))
        if len(images) == 0:
            raise ValueError("No images found in the input directory.")
    elif not isinstance(images, list):
        raise ValueError("images must be a list or a path to the image directory.")

    images.sort()

    frames = [Image.open(image) for image in images]
    frame_one = frames[0]
    frame_one.save(
        out_gif,
        format="GIF",
        append_images=frames,
        save_all=True,
        duration=int(1000 / fps),
        loop=loop,
    )

    if mp4:
        if not is_tool("ffmpeg"):
            print("ffmpeg is not installed on your computer.")
            return

        if os.path.exists(out_gif):
            out_mp4 = out_gif.replace(".gif", ".mp4")
            cmd = f"ffmpeg -loglevel error -i {out_gif} -vcodec libx264 -crf 25 -pix_fmt yuv420p {out_mp4}"
            os.system(cmd)
            if not os.path.exists(out_mp4):
                raise Exception(f"Failed to create mp4 file.")
    if clean_up:
        for image in images:
            os.remove(image)


def gif_to_mp4(in_gif, out_mp4):
    """Converts a gif to mp4.

    Args:
        in_gif (str): The input gif file.
        out_mp4 (str): The output mp4 file.
    """
    from PIL import Image

    if not os.path.exists(in_gif):
        raise FileNotFoundError(f"{in_gif} does not exist.")

    out_mp4 = os.path.abspath(out_mp4)
    if not out_mp4.endswith(".mp4"):
        out_mp4 = out_mp4 + ".mp4"

    if not os.path.exists(os.path.dirname(out_mp4)):
        os.makedirs(os.path.dirname(out_mp4))

    if not is_tool("ffmpeg"):
        print("ffmpeg is not installed on your computer.")
        return

    width, height = Image.open(in_gif).size

    if width % 2 == 0 and height % 2 == 0:
        cmd = f"ffmpeg -loglevel error -i {in_gif} -vcodec libx264 -crf 25 -pix_fmt yuv420p {out_mp4}"
        os.system(cmd)
    else:
        width += width % 2
        height += height % 2
        cmd = f"ffmpeg -loglevel error -i {in_gif} -vf scale={width}:{height} -vcodec libx264 -crf 25 -pix_fmt yuv420p {out_mp4}"
        os.system(cmd)

    if not os.path.exists(out_mp4):
        raise Exception(f"Failed to create mp4 file.")


def merge_gifs(in_gifs, out_gif):
    """Merge multiple gifs into one.

    Args:
        in_gifs (str | list): The input gifs as a list or a directory path.
        out_gif (str): The output gif.

    Raises:
        Exception:  Raise exception when gifsicle is not installed.
    """
    import glob

    try:
        if isinstance(in_gifs, str) and os.path.isdir(in_gifs):
            in_gifs = glob.glob(os.path.join(in_gifs, "*.gif"))
        elif not isinstance(in_gifs, list):
            raise Exception("in_gifs must be a list.")

        in_gifs = " ".join(in_gifs)

        cmd = f"gifsicle {in_gifs} > {out_gif}"
        os.system(cmd)

    except Exception as e:
        print(
            "gifsicle is not installed. Run 'sudo apt-get install -y gifsicle' to install it."
        )
        print(e)


def gif_to_png(in_gif, out_dir=None, prefix="", verbose=True):
    """Converts a gif to png.

    Args:
        in_gif (str): The input gif file.
        out_dir (str, optional): The output directory. Defaults to None.
        prefix (str, optional): The prefix of the output png files. Defaults to None.
        verbose (bool, optional): Whether to print the progress. Defaults to True.

    Raises:
        FileNotFoundError: Raise exception when the input gif does not exist.
        Exception: Raise exception when ffmpeg is not installed.
    """
    import tempfile

    in_gif = os.path.abspath(in_gif)
    if " " in in_gif:
        raise Exception("in_gif cannot contain spaces.")
    if not os.path.exists(in_gif):
        raise FileNotFoundError(f"{in_gif} does not exist.")

    basename = os.path.basename(in_gif).replace(".gif", "")
    if out_dir is None:
        out_dir = os.path.join(tempfile.gettempdir(), basename)
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
    elif isinstance(out_dir, str) and not os.path.exists(out_dir):
        os.makedirs(out_dir)
    elif not isinstance(out_dir, str):
        raise Exception("out_dir must be a string.")

    out_dir = os.path.abspath(out_dir)
    cmd = f"ffmpeg -loglevel error -i {in_gif} -vsync 0 {out_dir}/{prefix}%d.png"
    os.system(cmd)

    if verbose:
        print(f"Images are saved to {out_dir}")


def gif_fading(in_gif, out_gif, duration=1, verbose=True):
    """Fade in/out the gif.

    Args:
        in_gif (str): The input gif file. Can be a directory path or http URL, e.g., "https://i.imgur.com/ZWSZC5z.gif"
        out_gif (str): The output gif file.
        duration (float, optional): The duration of the fading. Defaults to 1.
        verbose (bool, optional): Whether to print the progress. Defaults to True.

    Raises:
        FileNotFoundError: Raise exception when the input gif does not exist.
        Exception: Raise exception when ffmpeg is not installed.
    """
    import glob
    import tempfile

    current_dir = os.getcwd()

    if isinstance(in_gif, str) and in_gif.startswith("http"):
        ext = os.path.splitext(in_gif)[1]
        file_path = temp_file_path(ext)
        download_from_url(in_gif, file_path, verbose=verbose)
        in_gif = file_path

    in_gif = os.path.abspath(in_gif)
    if not in_gif.endswith(".gif"):
        raise Exception("in_gif must be a gif file.")

    if " " in in_gif:
        raise Exception("The filename cannot contain spaces.")

    out_gif = os.path.abspath(out_gif)
    if not os.path.exists(os.path.dirname(out_gif)):
        os.makedirs(os.path.dirname(out_gif))

    if not os.path.exists(in_gif):
        raise FileNotFoundError(f"{in_gif} does not exist.")

    basename = os.path.basename(in_gif).replace(".gif", "")
    temp_dir = os.path.join(tempfile.gettempdir(), basename)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    gif_to_png(in_gif, temp_dir, verbose=verbose)

    os.chdir(temp_dir)

    images = list(glob.glob(os.path.join(temp_dir, "*.png")))
    count = len(images)

    files = []
    for i in range(1, count + 1):
        files.append(f"-loop 1 -t {duration} -i {i}.png")
    inputs = " ".join(files)

    filters = []
    for i in range(1, count):
        if i == 1:
            filters.append(
                f"\"[1:v][0:v]blend=all_expr='A*(if(gte(T,3),1,T/3))+B*(1-(if(gte(T,3),1,T/3)))'[v0];"
            )
        else:
            filters.append(
                f"[{i}:v][{i-1}:v]blend=all_expr='A*(if(gte(T,3),1,T/3))+B*(1-(if(gte(T,3),1,T/3)))'[v{i-1}];"
            )

    last_filter = ""
    for i in range(count - 1):
        last_filter += f"[v{i}]"
    last_filter += f'concat=n={count-1}:v=1:a=0[v]" -map "[v]"'
    filters.append(last_filter)
    filters = " ".join(filters)

    cmd = f"ffmpeg -y -loglevel error {inputs} -filter_complex {filters} {out_gif}"

    # if fade >= duration:
    #     duration = fade + 1

    # files = []
    # for i in range(1, count + 1):
    #     files.append(f"-framerate {framerate} -loop 1 -t {duration} -i {i}.png")

    # inputs = " ".join(files)

    # filters = []
    # for i in range(count):
    #     if i == 0:
    #         filters.append(f'"[0:v]fade=t=out:st=4:d={fade}[v0];')
    #     else:
    #         filters.append(
    #             f"[{i}:v]fade=t=in:st=0:d={fade},fade=t=out:st=4:d={fade}[v{i}];"
    #         )

    # last_filter = ""
    # for i in range(count):
    #     last_filter += f"[v{i}]"
    # last_filter += f"concat=n={count}:v=1:a=0,split[v0][v1];"
    # filters.append(last_filter)
    # palette = f'[v0]palettegen[p];[v1][p]paletteuse[v]" -map "[v]"'
    # filters.append(palette)
    # filters = " ".join(filters)

    # cmd = f"ffmpeg -y {inputs} -filter_complex {filters} {out_gif}"

    os.system(cmd)
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        print(e)

    os.chdir(current_dir)


def add_text_to_gif(
    in_gif,
    out_gif,
    xy=None,
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="#000000",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    duration=100,
    loop=0,
):
    """Adds animated text to a GIF image.

    Args:
        in_gif (str): The file path to the input GIF image.
        out_gif (str): The file path to the output GIF image.
        xy (tuple, optional): Top left corner of the text. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        duration (int, optional): controls how long each frame will be displayed for, in milliseconds. It is the inverse of the frame rate. Setting it to 100 milliseconds gives 10 frames per second. You can decrease the duration to give a smoother animation.. Defaults to 100.
        loop (int, optional): controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.

    """
    # import io
    import warnings

    import importlib.resources
    from PIL import Image, ImageDraw, ImageFont, ImageSequence

    warnings.simplefilter("ignore")

    pkg_dir = str(importlib.resources.files("geemap").joinpath("geemap.py").parent)
    default_font = os.path.join(pkg_dir, "data/fonts/arial.ttf")

    in_gif = os.path.abspath(in_gif)
    out_gif = os.path.abspath(out_gif)

    if not os.path.exists(in_gif):
        print("The input gif file does not exist.")
        return

    if not os.path.exists(os.path.dirname(out_gif)):
        os.makedirs(os.path.dirname(out_gif))

    if font_type == "arial.ttf":
        font = ImageFont.truetype(default_font, font_size)
    elif font_type == "alibaba.otf":
        default_font = os.path.join(pkg_dir, "data/fonts/alibaba.otf")
        font = ImageFont.truetype(default_font, font_size)
    else:
        try:
            font_list = system_fonts(show_full_path=True)
            font_names = [os.path.basename(f) for f in font_list]
            if (font_type in font_list) or (font_type in font_names):
                font = ImageFont.truetype(font_type, font_size)
            else:
                print(
                    "The specified font type could not be found on your system. Using the default font instead."
                )
                font = ImageFont.truetype(default_font, font_size)
        except Exception as e:
            print(e)
            font = ImageFont.truetype(default_font, font_size)

    color = check_color(font_color)
    progress_bar_color = check_color(progress_bar_color)

    try:
        image = Image.open(in_gif)
    except Exception as e:
        print("An error occurred while opening the gif.")
        print(e)
        return

    count = image.n_frames
    W, H = image.size
    progress_bar_widths = [i * 1.0 / count * W for i in range(1, count + 1)]
    progress_bar_shapes = [
        [(0, H - progress_bar_height), (x, H)] for x in progress_bar_widths
    ]

    if xy is None:
        # default text location is 5% width and 5% height of the image.
        xy = (int(0.05 * W), int(0.05 * H))
    elif (xy is not None) and (not isinstance(xy, tuple)) and (len(xy) == 2):
        print("xy must be a tuple, e.g., (10, 10), ('10%', '10%')")
        return
    elif all(isinstance(item, int) for item in xy) and (len(xy) == 2):
        x, y = xy
        if (x > 0) and (x < W) and (y > 0) and (y < H):
            pass
        else:
            print(
                f"xy is out of bounds. x must be within [0, {W}], and y must be within [0, {H}]"
            )
            return
    elif all(isinstance(item, str) for item in xy) and (len(xy) == 2):
        x, y = xy
        if ("%" in x) and ("%" in y):
            try:
                x = int(float(x.replace("%", "")) / 100.0 * W)
                y = int(float(y.replace("%", "")) / 100.0 * H)
                xy = (x, y)
            except Exception:
                raise Exception(
                    "The specified xy is invalid. It must be formatted like this ('10%', '10%')"
                )
    else:
        print(
            "The specified xy is invalid. It must be formatted like this: (10, 10) or ('10%', '10%')"
        )
        return

    if text_sequence is None:
        text = [str(x) for x in range(1, count + 1)]
    elif isinstance(text_sequence, int):
        text = [str(x) for x in range(text_sequence, text_sequence + count + 1)]
    elif isinstance(text_sequence, str):
        try:
            text_sequence = int(text_sequence)
            text = [str(x) for x in range(text_sequence, text_sequence + count + 1)]
        except Exception:
            text = [text_sequence] * count
    elif isinstance(text_sequence, list) and len(text_sequence) != count:
        print(
            f"The length of the text sequence must be equal to the number ({count}) of frames in the gif."
        )
        return
    else:
        text = [str(x) for x in text_sequence]

    try:
        frames = []
        # Loop over each frame in the animated image
        for index, frame in enumerate(ImageSequence.Iterator(image)):
            # Draw the text on the frame
            frame = frame.convert("RGB")
            draw = ImageDraw.Draw(frame)
            # w, h = draw.textsize(text[index])
            draw.text(xy, text[index], font=font, fill=color)
            if add_progress_bar:
                draw.rectangle(progress_bar_shapes[index], fill=progress_bar_color)
            del draw

            b = io.BytesIO()
            frame.save(b, format="GIF")
            frame = Image.open(b)

            frames.append(frame)
        # https://www.pythoninformer.com/python-libraries/pillow/creating-animated-gif/
        # Save the frames as a new image

        frames[0].save(
            out_gif,
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=loop,
            optimize=True,
        )
    except Exception as e:
        print(e)


def add_image_to_gif(
    in_gif, out_gif, in_image, xy=None, image_size=(80, 80), circle_mask=False
):
    """Adds an image logo to a GIF image.

    Args:
        in_gif (str): Input file path to the GIF image.
        out_gif (str): Output file path to the GIF image.
        in_image (str): Input file path to the image.
        xy (tuple, optional): Top left corner of the text. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        image_size (tuple, optional): Resize image. Defaults to (80, 80).
        circle_mask (bool, optional): Whether to apply a circle mask to the image. This only works with non-png images. Defaults to False.
    """
    # import io
    import warnings

    from PIL import Image, ImageDraw, ImageSequence

    warnings.simplefilter("ignore")

    in_gif = os.path.abspath(in_gif)

    is_url = False
    if in_image.startswith("http"):
        is_url = True

    if not os.path.exists(in_gif):
        print("The input gif file does not exist.")
        return

    if (not is_url) and (not os.path.exists(in_image)):
        print("The provided logo file does not exist.")
        return

    out_dir = check_dir((os.path.dirname(out_gif)))
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    try:
        gif = Image.open(in_gif)
    except Exception as e:
        print("An error occurred while opening the image.")
        print(e)
        return

    logo_raw_image = None
    try:
        if in_image.startswith("http"):
            logo_raw_image = open_image_from_url(in_image)
        else:
            in_image = os.path.abspath(in_image)
            logo_raw_image = Image.open(in_image)
    except Exception as e:
        print(e)

    logo_raw_size = logo_raw_image.size

    ratio = max(
        logo_raw_size[0] / image_size[0],
        logo_raw_size[1] / image_size[1],
    )
    image_resize = (int(logo_raw_size[0] / ratio), int(logo_raw_size[1] / ratio))
    image_size = min(logo_raw_size[0], image_size[0]), min(
        logo_raw_size[1], image_size[1]
    )

    logo_image = logo_raw_image.convert("RGBA")
    logo_image.thumbnail(image_size, Image.LANCZOS)

    gif_width, gif_height = gif.size
    mask_im = None

    if circle_mask:
        mask_im = Image.new("L", image_size, 0)
        draw = ImageDraw.Draw(mask_im)
        draw.ellipse((0, 0, image_size[0], image_size[1]), fill=255)

    if has_transparency(logo_raw_image):
        mask_im = logo_image.copy()

    if xy is None:
        # default logo location is 5% width and 5% height of the image.
        delta = 10
        xy = (gif_width - image_resize[0] - delta, gif_height - image_resize[1] - delta)
        # xy = (int(0.05 * gif_width), int(0.05 * gif_height))
    elif (xy is not None) and (not isinstance(xy, tuple)) and (len(xy) == 2):
        print("xy must be a tuple, e.g., (10, 10), ('10%', '10%')")
        return
    elif all(isinstance(item, int) for item in xy) and (len(xy) == 2):
        x, y = xy
        if (x > 0) and (x < gif_width) and (y > 0) and (y < gif_height):
            pass
        else:
            print(
                "xy is out of bounds. x must be within [0, {}], and y must be within [0, {}]".format(
                    gif_width, gif_height
                )
            )
            return
    elif all(isinstance(item, str) for item in xy) and (len(xy) == 2):
        x, y = xy
        if ("%" in x) and ("%" in y):
            try:
                x = int(float(x.replace("%", "")) / 100.0 * gif_width)
                y = int(float(y.replace("%", "")) / 100.0 * gif_height)
                xy = (x, y)
            except Exception:
                raise Exception(
                    "The specified xy is invalid. It must be formatted like this ('10%', '10%')"
                )

    else:
        raise Exception(
            "The specified xy is invalid. It must be formatted like this: (10, 10) or ('10%', '10%')"
        )

    try:
        frames = []
        for _, frame in enumerate(ImageSequence.Iterator(gif)):
            frame = frame.convert("RGBA")
            frame.paste(logo_image, xy, mask_im)

            b = io.BytesIO()
            frame.save(b, format="GIF")
            frame = Image.open(b)
            frames.append(frame)

        frames[0].save(out_gif, save_all=True, append_images=frames[1:])
    except Exception as e:
        print(e)


def reduce_gif_size(in_gif, out_gif=None):
    """Reduces a GIF image using ffmpeg.

    Args:
        in_gif (str): The input file path to the GIF image.
        out_gif (str, optional): The output file path to the GIF image. Defaults to None.
    """
    import ffmpeg
    import warnings

    warnings.filterwarnings("ignore")

    if not is_tool("ffmpeg"):
        print("ffmpeg is not installed on your computer.")
        return

    if not os.path.exists(in_gif):
        print("The input gif file does not exist.")
        return

    if out_gif is None:
        out_gif = in_gif
    elif not os.path.exists(os.path.dirname(out_gif)):
        os.makedirs(os.path.dirname(out_gif))

    if in_gif == out_gif:
        tmp_gif = in_gif.replace(".gif", "_tmp.gif")
        shutil.copyfile(in_gif, tmp_gif)
        stream = ffmpeg.input(tmp_gif)
        stream = ffmpeg.output(stream, in_gif, loglevel="quiet").overwrite_output()
        ffmpeg.run(stream)
        os.remove(tmp_gif)

    else:
        stream = ffmpeg.input(in_gif)
        stream = ffmpeg.output(stream, out_gif, loglevel="quiet").overwrite_output()
        ffmpeg.run(stream)


def create_timeseries(
    collection,
    start_date,
    end_date,
    region=None,
    bands=None,
    frequency="year",
    reducer="median",
    drop_empty=True,
    date_format=None,
    parallel_scale=1,
    step=1,
):
    """Creates a timeseries from a collection of images by a specified frequency and reducer.

    Args:
        collection (str | ee.ImageCollection): The collection of images to create a timeseries from. It can be a string representing the collection ID or an ee.ImageCollection object.
        start_date (str): The start date of the timeseries. It must be formatted like this: 'YYYY-MM-dd'.
        end_date (str): The end date of the timeseries. It must be formatted like this: 'YYYY-MM-dd'.
        region (ee.Geometry, optional): The region to use to filter the collection of images. It must be an ee.Geometry object. Defaults to None.
        bands (list, optional): The list of bands to use to create the timeseries. It must be a list of strings. Defaults to None.
        frequency (str, optional): The frequency of the timeseries. It must be one of the following: 'year', 'month', 'day', 'hour', 'minute', 'second'. Defaults to 'year'.
        reducer (str, optional):  The reducer to use to reduce the collection of images to a single value. It can be one of the following: 'median', 'mean', 'min', 'max', 'variance', 'sum'. Defaults to 'median'.
        drop_empty (bool, optional): Whether to drop empty images from the timeseries. Defaults to True.
        date_format (str, optional): A pattern, as described at http://joda-time.sourceforge.net/apidocs/org/joda/time/format/DateTimeFormat.html. Defaults to 'YYYY-MM-dd'.
        parallel_scale (int, optional): A scaling factor used to limit memory use; using a larger parallel_scale (e.g. 2 or 4) may enable computations that run out of memory with the default. Defaults to 1.
        step (int, optional): The step size to use when creating the date sequence. Defaults to 1.

    Returns:
        ee.ImageCollection: The timeseries.
    """
    if not isinstance(collection, ee.ImageCollection):
        if isinstance(collection, str):
            collection = ee.ImageCollection(collection)
        else:
            raise Exception(
                "The collection must be an ee.ImageCollection object or asset id."
            )

    if bands is not None:
        collection = collection.select(bands)
    else:
        bands = collection.first().bandNames()

    feq_dict = {
        "year": "YYYY",
        "month": "YYYY-MM",
        "quarter": "YYYY-MM",
        "week": "YYYY-MM-dd",
        "day": "YYYY-MM-dd",
        "hour": "YYYY-MM-dd HH",
        "minute": "YYYY-MM-dd HH:mm",
        "second": "YYYY-MM-dd HH:mm:ss",
    }

    if date_format is None:
        date_format = feq_dict[frequency]

    dates = date_sequence(start_date, end_date, frequency, date_format, step)

    try:
        reducer = eval(f"ee.Reducer.{reducer}()")
    except Exception as e:
        print("The provided reducer is invalid.")
        raise Exception(e)

    def create_image(date):
        start = ee.Date(date)
        if frequency == "quarter":
            end = start.advance(3, "month")
        else:
            end = start.advance(1, frequency)

        if region is None:
            sub_col = collection.filterDate(start, end)
            image = sub_col.reduce(reducer, parallel_scale)

        else:
            sub_col = collection.filterDate(start, end).filterBounds(region)
            image = ee.Image(
                ee.Algorithms.If(
                    ee.Algorithms.ObjectType(region).equals("FeatureCollection"),
                    sub_col.reduce(reducer, parallel_scale).clipToCollection(region),
                    sub_col.reduce(reducer, parallel_scale).clip(region),
                )
            )
        return image.set(
            {
                "system:time_start": ee.Date(date).millis(),
                "system:date": ee.Date(date).format(date_format),
                "empty": sub_col.limit(1).size().eq(0),
            }
        ).rename(bands)

    try:
        images = ee.ImageCollection(dates.map(create_image))
        if drop_empty:
            return images.filterMetadata("empty", "equals", 0)
        else:
            return images
    except Exception as e:
        raise Exception(e)


def create_timelapse(
    collection,
    start_date,
    end_date,
    region=None,
    bands=None,
    frequency="year",
    reducer="median",
    date_format=None,
    out_gif=None,
    palette=None,
    vis_params=None,
    dimensions=768,
    frames_per_second=10,
    crs="EPSG:3857",
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    add_colorbar=False,
    colorbar_width=6.0,
    colorbar_height=0.4,
    colorbar_label=None,
    colorbar_label_size=12,
    colorbar_label_weight="normal",
    colorbar_tick_size=10,
    colorbar_bg_color=None,
    colorbar_orientation="horizontal",
    colorbar_dpi="figure",
    colorbar_xy=None,
    colorbar_size=(300, 300),
    loop=0,
    mp4=False,
    fading=False,
    parallel_scale=1,
    step=1,
):
    """Create a timelapse from any ee.ImageCollection.

    Args:
        collection (str | ee.ImageCollection): The collection of images to create a timeseries from. It can be a string representing the collection ID or an ee.ImageCollection object.
        start_date (str): The start date of the timeseries. It must be formatted like this: 'YYYY-MM-dd'.
        end_date (str): The end date of the timeseries. It must be formatted like this: 'YYYY-MM-dd'.
        region (ee.Geometry, optional): The region to use to filter the collection of images. It must be an ee.Geometry object. Defaults to None.
        bands (list, optional): A list of band names to use in the timelapse. Defaults to None.
        frequency (str, optional): The frequency of the timeseries. It must be one of the following: 'year', 'month', 'day', 'hour', 'minute', 'second'. Defaults to 'year'.
        reducer (str, optional):  The reducer to use to reduce the collection of images to a single value. It can be one of the following: 'median', 'mean', 'min', 'max', 'variance', 'sum'. Defaults to 'median'.
        drop_empty (bool, optional): Whether to drop empty images from the timeseries. Defaults to True.
        date_format (str, optional): A pattern, as described at http://joda-time.sourceforge.net/apidocs/org/joda/time/format/DateTimeFormat.html. Defaults to 'YYYY-MM-dd'.
        out_gif (str): The output gif file path. Defaults to None.
        palette (list, optional): A list of colors to render a single-band image in the timelapse. Defaults to None.
        vis_params (dict, optional): A dictionary of visualization parameters to use in the timelapse. Defaults to None. See more at https://developers.google.com/earth-engine/guides/image_visualization.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        crs (str, optional): The coordinate reference system to use. Defaults to "EPSG:3857".
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Lower left corner of the title. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        add_text (bool, optional): Whether to add animated text to the timelapse. Defaults to True.
        title_xy (tuple, optional): Lower left corner of the text sequency. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        add_colorbar (bool, optional): Whether to add a colorbar to the timelapse. Defaults to False.
        colorbar_width (float, optional): Width of the colorbar. Defaults to 6.0.
        colorbar_height (float, optional): Height of the colorbar. Defaults to 0.4.
        colorbar_label (str, optional): Label for the colorbar. Defaults to None.
        colorbar_label_size (int, optional): Font size for the colorbar label. Defaults to 12.
        colorbar_label_weight (str, optional): Font weight for the colorbar label. Defaults to 'normal'.
        colorbar_tick_size (int, optional): Font size for the colorbar ticks. Defaults to 10.
        colorbar_bg_color (str, optional): Background color for the colorbar, can be color like "white", "black". Defaults to None.
        colorbar_orientation (str, optional): Orientation of the colorbar. Defaults to 'horizontal'.
        colorbar_dpi (str, optional): DPI for the colorbar, can be numbers like 100, 300. Defaults to 'figure'.
        colorbar_xy (tuple, optional): Lower left corner of the colorbar. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        colorbar_size (tuple, optional): Size of the colorbar. It can be formatted like this: (300, 300). Defaults to (300, 300).
        loop (int, optional): Controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        mp4 (bool, optional): Whether to create an mp4 file. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).
        parallel_scale (int, optional): A scaling factor used to limit memory use; using a larger parallel_scale (e.g. 2 or 4) may enable computations that run out of memory with the default. Defaults to 1.
        step (int, optional): The step size to use when creating the date sequence. Defaults to 1.

    Returns:
        str: File path to the timelapse gif.
    """
    import geemap.colormaps as cm

    if not isinstance(collection, ee.ImageCollection):
        if isinstance(collection, str):
            collection = ee.ImageCollection(collection)
        else:
            raise Exception(
                "The collection must be an ee.ImageCollection object or asset id."
            )

    col = create_timeseries(
        collection,
        start_date,
        end_date,
        region=region,
        bands=bands,
        frequency=frequency,
        reducer=reducer,
        drop_empty=True,
        date_format=date_format,
        parallel_scale=parallel_scale,
        step=step,
    )

    # rename the bands to remove the '_reducer' characters from the band names.
    col = col.map(
        lambda img: img.rename(
            img.bandNames().map(lambda name: ee.String(name).replace(f"_{reducer}", ""))
        )
    )

    if out_gif is None:
        out_gif = temp_file_path(".gif")
    else:
        out_gif = check_file_path(out_gif)

    out_dir = os.path.dirname(out_gif)

    if bands is None:
        names = col.first().bandNames().getInfo()
        if len(names) < 3:
            bands = [names[0]]
        else:
            bands = names[:3][::-1]
    elif isinstance(bands, str):
        bands = [bands]
    elif not isinstance(bands, list):
        raise Exception("The bands must be a string or a list of strings.")

    if isinstance(palette, str):
        palette = cm.get_palette(palette, 15)
    elif isinstance(palette, list) or isinstance(palette, tuple):
        pass
    elif palette is not None:
        raise Exception("The palette must be a string or a list of strings.")

    if vis_params is None:
        img = col.first().select(bands)
        scale = collection.first().select(0).projection().nominalScale().multiply(10)
        min_value = min(
            image_min_value(img, region=region, scale=scale).getInfo().values()
        )
        max_value = max(
            image_max_value(img, region=region, scale=scale).getInfo().values()
        )
        vis_params = {"bands": bands, "min": min_value, "max": max_value}

        if len(bands) == 1:
            if palette is not None:
                vis_params["palette"] = palette
            else:
                vis_params["palette"] = cm.palettes.ndvi
    elif isinstance(vis_params, dict):
        if "bands" not in vis_params:
            vis_params["bands"] = bands
        if "min" not in vis_params:
            img = col.first().select(bands)
            scale = (
                collection.first().select(0).projection().nominalScale().multiply(10)
            )
            vis_params["min"] = min(
                image_min_value(img, region=region, scale=scale).getInfo().values()
            )
        if "max" not in vis_params:
            img = col.first().select(bands)
            scale = (
                collection.first().select(0).projection().nominalScale().multiply(10)
            )
            vis_params["max"] = max(
                image_max_value(img, region=region, scale=scale).getInfo().values()
            )
        if palette is None and (len(bands) == 1) and ("palette" not in vis_params):
            vis_params["palette"] = cm.palettes.ndvi
        elif palette is not None and ("palette" not in vis_params):
            vis_params["palette"] = palette
        if len(bands) > 1 and "palette" in vis_params:
            del vis_params["palette"]
    else:
        raise Exception("The vis_params must be a dictionary.")

    col = col.select(bands).map(
        lambda img: img.visualize(**vis_params).set(
            {
                "system:time_start": img.get("system:time_start"),
                "system:date": img.get("system:date"),
            }
        )
    )

    if overlay_data is not None:
        col = add_overlay(
            col, overlay_data, overlay_color, overlay_width, overlay_opacity
        )

    video_args = {}
    video_args["dimensions"] = dimensions
    video_args["region"] = region
    video_args["framesPerSecond"] = frames_per_second
    video_args["crs"] = crs
    video_args["min"] = 0
    video_args["max"] = 255

    # if crs is not None:
    #     video_args["crs"] = crs

    if "palette" in vis_params or len(bands) > 1:
        video_args["bands"] = ["vis-red", "vis-green", "vis-blue"]
    else:
        video_args["bands"] = ["vis-gray"]

    if (
        isinstance(dimensions, int)
        and dimensions > 768
        or isinstance(dimensions, str)
        and any(dim > 768 for dim in list(map(int, dimensions.split("x"))))
    ):
        count = col.size().getInfo()
        basename = os.path.basename(out_gif)[:-4]
        names = [
            os.path.join(
                out_dir, f"{basename}_{str(i+1).zfill(int(len(str(count))))}.jpg"
            )
            for i in range(count)
        ]
        get_image_collection_thumbnails(
            col,
            out_dir,
            vis_params={
                "min": 0,
                "max": 255,
                "bands": video_args["bands"],
            },
            dimensions=dimensions,
            names=names,
        )
        make_gif(
            names,
            out_gif,
            fps=frames_per_second,
            loop=loop,
            mp4=False,
            clean_up=True,
        )
    else:
        download_ee_video(col, video_args, out_gif)

    if title is not None and isinstance(title, str):
        add_text_to_gif(
            out_gif,
            out_gif,
            xy=title_xy,
            text_sequence=title,
            font_type=font_type,
            font_size=font_size,
            font_color=font_color,
            add_progress_bar=add_progress_bar,
            progress_bar_color=progress_bar_color,
            progress_bar_height=progress_bar_height,
            duration=1000 / frames_per_second,
            loop=loop,
        )
    if add_text:
        if text_sequence is None:
            text_sequence = col.aggregate_array("system:date").getInfo()
        add_text_to_gif(
            out_gif,
            out_gif,
            xy=text_xy,
            text_sequence=text_sequence,
            font_type=font_type,
            font_size=font_size,
            font_color=font_color,
            add_progress_bar=add_progress_bar,
            progress_bar_color=progress_bar_color,
            progress_bar_height=progress_bar_height,
            duration=1000 / frames_per_second,
            loop=loop,
        )
    if add_colorbar:
        colorbar = save_colorbar(
            None,
            colorbar_width,
            colorbar_height,
            vis_params["min"],
            vis_params["max"],
            vis_params["palette"],
            label=colorbar_label,
            label_size=colorbar_label_size,
            label_weight=colorbar_label_weight,
            tick_size=colorbar_tick_size,
            bg_color=colorbar_bg_color,
            orientation=colorbar_orientation,
            dpi=colorbar_dpi,
            show_colorbar=False,
        )
        add_image_to_gif(out_gif, out_gif, colorbar, colorbar_xy, colorbar_size)

    if os.path.exists(out_gif):
        reduce_gif_size(out_gif)

    if isinstance(fading, bool):
        fading = int(fading)
    if fading > 0:
        gif_fading(out_gif, out_gif, duration=fading, verbose=False)

    if mp4:
        out_mp4 = out_gif.replace(".gif", ".mp4")
        gif_to_mp4(out_gif, out_mp4)

    return out_gif


def naip_timeseries(roi=None, start_year=2003, end_year=None, RGBN=False, step=1):
    """Creates NAIP annual timeseries

    Args:
        roi (object, optional): An ee.Geometry representing the region of interest. Defaults to None.
        start_year (int, optional): Starting year for the timeseries. Defaults to 2003.
        end_year (int, optional): Ending year for the timeseries. Defaults to None, which will use the current year.
        RGBN (bool, optional): Whether to retrieve 4-band NAIP imagery only.
        step (int, optional): The step size to use when creating the date sequence. Defaults to 1.
    Returns:
        object: An ee.ImageCollection representing annual NAIP imagery.
    """
    try:
        if end_year is None:
            end_year = datetime.datetime.now().year

        def get_annual_NAIP(year):
            try:
                collection = ee.ImageCollection("USDA/NAIP/DOQQ")
                if roi is not None:
                    collection = collection.filterBounds(roi)
                start_date = ee.Date.fromYMD(year, 1, 1)
                end_date = ee.Date.fromYMD(year, 12, 31)
                naip = collection.filterDate(start_date, end_date)
                if RGBN:
                    naip = naip.filter(ee.Filter.listContains("system:band_names", "N"))
                if roi is not None:
                    if isinstance(roi, ee.Geometry):
                        image = ee.Image(ee.ImageCollection(naip).mosaic().clip(roi))
                    elif isinstance(roi, ee.FeatureCollection):
                        image = ee.Image(
                            ee.ImageCollection(naip).mosaic().clipToCollection(roi)
                        )
                else:
                    image = ee.Image(ee.ImageCollection(naip).mosaic())
                return image.set(
                    {
                        "system:time_start": ee.Date(start_date).millis(),
                        "system:time_end": ee.Date(end_date).millis(),
                        "empty": naip.size().eq(0),
                    }
                )
            except Exception as e:
                raise Exception(e)

        years = ee.List.sequence(start_year, end_year, step)
        collection = ee.ImageCollection(years.map(get_annual_NAIP))
        return collection.filterMetadata("empty", "equals", 0)

    except Exception as e:
        raise Exception(e)


def naip_timelapse(
    roi,
    start_year=2003,
    end_year=None,
    out_gif=None,
    bands=None,
    palette=None,
    vis_params=None,
    dimensions=768,
    frames_per_second=3,
    crs="EPSG:3857",
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    loop=0,
    mp4=False,
    fading=False,
    step=1,
):
    """Create a timelapse from NAIP imagery.

    Args:
        roi (ee.Geometry): The region to use to filter the collection of images. It must be an ee.Geometry object. Defaults to None.
        start_year (int | str, optional): The start year of the timeseries. It must be formatted like this: 'YYYY'. Defaults to 2003.
        end_year (int | str, optional): The end year of the timeseries. It must be formatted like this: 'YYYY'. Defaults to None, which will use the current year.
        out_gif (str): The output gif file path. Defaults to None.
        bands (list, optional): A list of band names to use in the timelapse. Defaults to None.
        palette (list, optional): A list of colors to render a single-band image in the timelapse. Defaults to None.
        vis_params (dict, optional): A dictionary of visualization parameters to use in the timelapse. Defaults to None. See more at https://developers.google.com/earth-engine/guides/image_visualization.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        crs (str, optional): The coordinate reference system to use. Defaults to "EPSG:3857".
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Lower left corner of the title. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        add_text (bool, optional): Whether to add animated text to the timelapse. Defaults to True.
        title_xy (tuple, optional): Lower left corner of the text sequency. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        loop (int, optional): Controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        mp4 (bool, optional): Whether to create an mp4 file. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).
        step (int, optional): The step size to use when creating the date sequence. Defaults to 1.

    Returns:
        str: File path to the timelapse gif.
    """

    try:
        if end_year is None:
            end_year = datetime.datetime.now().year

        collection = ee.ImageCollection("USDA/NAIP/DOQQ")
        start_date = str(start_year) + "-01-01"
        end_date = str(end_year) + "-12-31"
        frequency = "year"
        reducer = "median"
        date_format = "YYYY"

        if bands is not None and isinstance(bands, list) and "N" in bands:
            collection = collection.filter(
                ee.Filter.listContains("system:band_names", "N")
            )

        return create_timelapse(
            collection,
            start_date,
            end_date,
            roi,
            bands,
            frequency,
            reducer,
            date_format,
            out_gif,
            palette,
            vis_params,
            dimensions,
            frames_per_second,
            crs,
            overlay_data,
            overlay_color,
            overlay_width,
            overlay_opacity,
            title,
            title_xy,
            add_text,
            text_xy,
            text_sequence,
            font_type,
            font_size,
            font_color,
            add_progress_bar,
            progress_bar_color,
            progress_bar_height,
            loop=loop,
            mp4=mp4,
            fading=fading,
            step=step,
        )

    except Exception as e:
        raise Exception(e)


def valid_roi(roi):
    if not isinstance(roi, ee.Geometry):
        try:
            roi = roi.geometry()
        except Exception as e:
            print("Could not convert the provided roi to ee.Geometry")
            print(e)
            return
    # Adjusts longitudes less than -180 degrees or greater than 180 degrees.
    geojson = ee_to_geojson(roi)
    geojson = adjust_longitude(geojson)
    return ee.Geometry(geojson)


def sentinel1_defaults():
    from datetime import date

    year = date.today().year
    roi = ee.Geometry.Polygon(
        [
            [
                [-115.471773, 35.892718],
                [-115.471773, 36.409454],
                [-114.271283, 36.409454],
                [-114.271283, 35.892718],
                [-115.471773, 35.892718],
            ]
        ],
        None,
        False,
    )
    return year, roi


def sentinel1_filtering(
    collection,
    band="VV",
    instrumentMode=None,
    orbitProperties_pass=None,
    transmitterReceiverPolarisation=None,
    remove_outliers=True,
    **kwargs,
):
    """
    Sentinel-1 data is collected with several different instrument configurations, resolutions,
    band combinations during both ascending and descending orbits. Because of this heterogeneity,
    it's usually necessary to filter the data down to a homogeneous subset before starting processing.

    For more details, see https://developers.google.com/earth-engine/guides/sentinel1

    Args:
        collection: A Sentinel1 ImageCollection to filter.
        band (str): Collection band. Can be one of ['HH','HV','VV','VH']. Defaults to 'VV' which is most commonly available on land.
        instrumentMode (str, optional): Collection property. Can be one of ['IW','EW','SM']. Defaults to band default availability (IW for ['VV','VH'], EW for ['HH','HV']). IW is typically available for land. EW for icy regions.
        orbitProperties_pass (str|None, optional): Collection property. Can be one of ['ASCENDING', 'DESCENDING', None]. Default to 'ASCENDING'.
            Will return mixed property if set to None, which dampen elevation, and increase surface roughness/fractality visibility.
        transmitterReceiverPolarisation: Collection property List contains this value. Can be one of ['HH','HV','VV','VH']. Defaults to band.
        remove_outliers (bool, optional): Remove pixels with extreme values (< -30). These can occur near the edge of an image. Default to True.
        **kwargs (dict, optional): All other arguments will be applied as filters to collection properties. F.e. {'resolution_meters':10}
            Full list properties: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD#image-properties

    Returns:
        object: Returns a homogeneous ImageCollection of Sentinel 1 images.
    """

    transmitterReceiverPolarisation = transmitterReceiverPolarisation or band
    instrumentMode = (
        instrumentMode or {"VV": "IW", "VH": "IW", "HH": "EW", "HV": "EW"}[band]
    )

    def remove_outliers_func(image):
        if not remove_outliers:
            return image
        edge = image.select(band).lt(-30.0)
        maskedimage = image.mask().And(edge.Not())
        return image.updateMask(maskedimage)

    col = collection.filter(ee.Filter.eq("instrumentMode", instrumentMode)).filter(
        ee.Filter.listContains(
            "transmitterReceiverPolarisation", transmitterReceiverPolarisation
        )
    )

    if remove_outliers:
        col = col.map(remove_outliers_func)

    for k, v in kwargs.items():
        col = col.filter(ee.Filter.eq(k, v))
    if orbitProperties_pass:
        col = col.filter(ee.Filter.eq("orbitProperties_pass", orbitProperties_pass))

    return col


def sentinel1_timeseries(
    roi=None,
    start_year=2015,
    end_year=None,
    start_date="01-01",
    end_date="12-31",
    frequency="year",
    clip=False,
    band="VV",
    orbit=["ascending", "descending"],
    **kwargs,
):
    """
    Generates a Sentinel 1 ImageCollection,
    based on mean composites following a steady frequency (f.e. 1 image per month)
    Adapted from https://code.earthengine.google.com/?scriptPath=Examples:Datasets/COPERNICUS_S1_GRD
    Args:
        roi (object, optional): Region of interest to create the timelapse. Defaults to a polygon partially covering Las Vegas and Lake Mead.
        start_year (int, optional): Starting year for the timelapse. Defaults to 2015.
        end_year (int, optional): Ending year for the timelapse. Defaults to current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '01-01'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '12-31'.
        frequency (str, optional): Frequency of the timelapse. Defaults to 'year'.  Can be 'year', 'quarter' or 'month'.
        clip (bool, optional): Whether to clip images to ROI. Defaults to False.
        band (str): Collection band. Can be one of ['HH','HV','VV','VH']. Defaults to 'VV' which is most commonly available on land.
        orbit (list, optional): List of orbit directions to include. Can be ['ascending'], ['descending'], or ['ascending', 'descending']. Defaults to both.
        **kwargs: Arguments for sentinel1_filtering().
    Returns:
        object: Returns an ImageCollection of Sentinel 1 images.
    """
    CURRENT_YEAR, ROI_DEFAULT = sentinel1_defaults()
    roi = roi or ROI_DEFAULT
    end_year = end_year or CURRENT_YEAR
    roi = valid_roi(roi)
    start = f"{start_year}-{start_date}"
    end = f"{end_year}-{end_date}"
    dates = date_sequence(start, end, frequency)

    # Load and filter Sentinel-1 collection
    col = ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(roi)

    # Apply orbit filtering
    if orbit:
        # Convert orbit strings to uppercase for consistency
        orbit_upper = [o.upper() for o in orbit]
        orbit_filter = ee.Filter.inList("orbitProperties_pass", orbit_upper)
        col = col.filter(orbit_filter)

    # Apply additional filtering and select band
    col = sentinel1_filtering(col, band=band, **kwargs).select(band)

    # Set up frequency parameters
    n = 1
    if frequency == "quarter":
        n = 3
        frequency = "month"

    def transform(date):
        start = date
        end = ee.Date(date).advance(n, frequency).advance(-1, "day")
        return (
            col.filterDate(start, end)
            .mean()
            .set(
                {
                    "system:time_start": ee.Date(start).millis(),
                    "system:time_end": ee.Date(end).millis(),
                    "system:date": start,
                }
            )
        )

    imgList = dates.map(lambda date: transform(date))
    imgColl = ee.ImageCollection.fromImages(imgList)

    if clip:
        imgColl = imgColl.map(lambda img: img.clip(roi))

    return imgColl


def sentinel2_timeseries(
    roi,
    start_year=2015,
    end_year=None,
    start_date="01-01",
    end_date="12-31",
    bands=None,
    mask_cloud=True,
    cloud_pct=30,
    frequency="year",
    reducer="median",
    drop_empty=True,
    date_format=None,
    parallel_scale=1,
    step=1,
):
    """Generates an annual Sentinel 2 ImageCollection. This algorithm is adapted from https://gist.github.com/jdbcode/76b9ac49faf51627ebd3ff988e10adbc. A huge thank you to Justin Braaten for sharing his fantastic work.
       Images include both level 1C and level 2A imagery.
    Args:

        roi (object, optional): Region of interest to create the timelapse. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 2015.
        end_year (int, optional): Ending year for the timelapse. Defaults to None, which will use the current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '01-01'.
        mask_cloud (bool, optional): Whether to mask clouds. Defaults to True.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '12-31'.
        bands (list, optional): The list of bands to use to create the timeseries. It must be a list of strings. Defaults to None.
        cloud_pct (int, optional): Maximum cloud percentage to include in the timelapse. Defaults to 30.
        frequency (str, optional): Frequency of the timelapse. Defaults to 'year'.
        reducer (str, optional):  The reducer to use to reduce the collection of images to a single value. It can be one of the following: 'median', 'mean', 'min', 'max', 'variance', 'sum'. Defaults to 'median'.
        drop_empty (bool, optional): Whether to drop empty images from the timeseries. Defaults to True.
        date_format (str, optional): Format of the date. Defaults to None.
        parallel_scale (int, optional): A scaling factor used to limit memory use; using a larger parallel_scale (e.g. 2 or 4) may enable computations that run out of memory with the default. Defaults to 1.
        step (int, optional): The step size to use when creating the date sequence. Defaults to 1.

    Returns:
        object: Returns an ImageCollection containing annual Sentinel 2 images.
    """
    if end_year is None:
        end_year = datetime.date.today().year

    def maskS2clouds(image):
        qa = image.select("QA60")

        # Bits 10 and 11 are clouds and cirrus, respectively.
        cloudBitMask = 1 << 10
        cirrusBitMask = 1 << 11

        # Both flags should be set to zero, indicating clear conditions.
        mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))

        return (
            image.updateMask(mask)
            .divide(10000)
            .set(image.toDictionary(image.propertyNames()))
        )

    start = f"{start_year}-{start_date}"
    end = f"{end_year}-{end_date}"
    doy_start = ee.Number.parse(ee.Date(start).format("D"))
    doy_end = ee.Number.parse(ee.Date(end).format("D"))
    collection = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterDate(start, end)
        .filter(ee.Filter.calendarRange(doy_start, doy_end, "day_of_year"))
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_pct))
        .filterBounds(roi)
    )

    if mask_cloud:
        collection = collection.map(maskS2clouds)
    else:
        collection = collection.map(
            lambda img: img.divide(10000).set(img.toDictionary(img.propertyNames()))
        )

    if bands is not None:
        allowed_bands = {
            "Blue": "B2",
            "Green": "B3",
            "Red": "B4",
            "Red Edge 1": "B5",
            "Red Edge 2": "B6",
            "Red Edge 3": "B7",
            "NIR": "B8",
            "Red Edge 4": "B8A",
            "SWIR1": "B11",
            "SWIR2": "B12",
            "QA60": "QA60",
        }

        for index, band in enumerate(bands):
            if band in allowed_bands:
                bands[index] = allowed_bands[band]

        collection = collection.select(bands)

    ts = create_timeseries(
        collection,
        start,
        end,
        roi,
        bands,
        frequency,
        reducer,
        drop_empty,
        date_format,
        parallel_scale,
        step,
    )
    return ts


def sentinel2_timeseries_legacy(
    roi=None,
    start_year=2015,
    end_year=None,
    start_date="01-01",
    end_date="12-31",
    apply_fmask=True,
    frequency="year",
    date_format=None,
):
    """Generates an annual Sentinel 2 ImageCollection. This algorithm is adapted from https://gist.github.com/jdbcode/76b9ac49faf51627ebd3ff988e10adbc. A huge thank you to Justin Braaten for sharing his fantastic work.
       Images include both level 1C and level 2A imagery.
    Args:

        roi (object, optional): Region of interest to create the timelapse. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 2015.
        end_year (int, optional): Ending year for the timelapse. Defaults to None, which will use the current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '01-01'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '12-31'.
        apply_fmask (bool, optional): Whether to apply Fmask (Function of mask) for automated clouds, cloud shadows, snow, and water masking.
        frequency (str, optional): Frequency of the timelapse. Defaults to 'year'.
        date_format (str, optional): Format of the date. Defaults to None.

    Returns:
        object: Returns an ImageCollection containing annual Sentinel 2 images.
    """
    ################################################################################

    ################################################################################
    # Input and output parameters.

    import re

    # import datetime

    if end_year is None:
        end_year = datetime.date.today().year

    if roi is None:
        roi = ee.Geometry.Polygon(
            [
                [
                    [-115.471773, 35.892718],
                    [-115.471773, 36.409454],
                    [-114.271283, 36.409454],
                    [-114.271283, 35.892718],
                    [-115.471773, 35.892718],
                ]
            ],
            None,
            False,
        )

    if not isinstance(roi, ee.Geometry):
        try:
            roi = roi.geometry()
        except Exception as e:
            print("Could not convert the provided roi to ee.Geometry")
            print(e)
            return

    # Adjusts longitudes less than -180 degrees or greater than 180 degrees.
    geojson = ee_to_geojson(roi)
    geojson = adjust_longitude(geojson)
    roi = ee.Geometry(geojson)

    feq_dict = {
        "year": "YYYY",
        "month": "YYYY-MM",
        "quarter": "YYYY-MM",
    }

    if date_format is None:
        date_format = feq_dict[frequency]

    if frequency not in feq_dict:
        raise ValueError("frequency must be year, quarter, or month.")

    ################################################################################
    # Setup vars to get dates.
    if (
        isinstance(start_year, int)
        and (start_year >= 2015)
        and (start_year <= get_current_year())
    ):
        pass
    else:
        print("The start year must be an integer >= 2015.")
        return

    if (
        isinstance(end_year, int)
        and (end_year >= 2015)
        and (end_year <= get_current_year())
    ):
        pass
    else:
        print(f"The end year must be an integer <= {get_current_year()}.")
        return

    if re.match(r"[0-9]{2}-[0-9]{2}", start_date) and re.match(
        r"[0-9]{2}-[0-9]{2}", end_date
    ):
        pass
    else:
        print("The start data and end date must be month-day, such as 06-10, 09-20")
        return

    try:
        datetime.datetime(int(start_year), int(start_date[:2]), int(start_date[3:5]))
        datetime.datetime(int(end_year), int(end_date[:2]), int(end_date[3:5]))
    except Exception as e:
        raise ValueError("The input dates are invalid.")

    try:
        start_test = datetime.datetime(
            int(start_year), int(start_date[:2]), int(start_date[3:5])
        )
        end_test = datetime.datetime(
            int(end_year), int(end_date[:2]), int(end_date[3:5])
        )
        if start_test > end_test:
            raise ValueError("Start date must be prior to end date")
    except Exception as e:
        raise Exception(e)

    def days_between(d1, d2):
        d1 = datetime.datetime.strptime(d1, "%Y-%m-%d")
        d2 = datetime.datetime.strptime(d2, "%Y-%m-%d")
        return abs((d2 - d1).days)

    n_days = days_between(
        str(start_year) + "-" + start_date, str(start_year) + "-" + end_date
    )
    start_month = int(start_date[:2])
    start_day = int(start_date[3:5])
    # start_date = str(start_year) + "-" + start_date
    # end_date = str(end_year) + "-" + end_date

    # # Define a collection filter by date, bounds, and quality.
    # def colFilter(col, aoi):  # , startDate, endDate):
    #     return(col.filterBounds(aoi))

    # Get Sentinel 2 collections, both Level-1C (top of atmophere) and Level-2A (surface reflectance)
    MSILCcol = ee.ImageCollection("COPERNICUS/S2")
    MSI2Acol = ee.ImageCollection("COPERNICUS/S2_SR")

    # Define a collection filter by date, bounds, and quality.
    def colFilter(col, roi, start_date, end_date):
        return col.filterBounds(roi).filterDate(start_date, end_date)
        # .filter('CLOUD_COVER < 5')
        # .filter('GEOMETRIC_RMSE_MODEL < 15')
        # .filter('IMAGE_QUALITY == 9 || IMAGE_QUALITY_OLI == 9'))

    # Function to get and rename bands of interest from MSI
    def renameMSI(img):
        return img.select(
            ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12", "QA60"],
            [
                "Blue",
                "Green",
                "Red",
                "Red Edge 1",
                "Red Edge 2",
                "Red Edge 3",
                "NIR",
                "Red Edge 4",
                "SWIR1",
                "SWIR2",
                "QA60",
            ],
        )

    # Add NBR for LandTrendr segmentation.

    def calcNbr(img):
        return img.addBands(
            img.normalizedDifference(["NIR", "SWIR2"]).multiply(-10000).rename("NBR")
        ).int16()

    # Define function to mask out clouds and cloud shadows in images.
    # Use CFmask band included in USGS Landsat SR image product.

    def fmask(img):
        cloudOpaqueBitMask = 1 << 10
        cloudCirrusBitMask = 1 << 11
        qa = img.select("QA60")
        mask = (
            qa.bitwiseAnd(cloudOpaqueBitMask)
            .eq(0)
            .And(qa.bitwiseAnd(cloudCirrusBitMask).eq(0))
        )
        return img.updateMask(mask)

    # Define function to prepare MSI images.
    def prepMSI(img):
        orig = img
        img = renameMSI(img)
        if apply_fmask:
            img = fmask(img)
        return ee.Image(img.copyProperties(orig, orig.propertyNames())).resample(
            "bicubic"
        )

    # Get annual median collection.
    def getAnnualComp(y):
        startDate = ee.Date.fromYMD(
            ee.Number(y), ee.Number(start_month), ee.Number(start_day)
        )
        endDate = startDate.advance(ee.Number(n_days), "day")

        # Filter collections and prepare them for merging.
        MSILCcoly = colFilter(MSILCcol, roi, startDate, endDate).map(prepMSI)
        MSI2Acoly = colFilter(MSI2Acol, roi, startDate, endDate).map(prepMSI)

        # Merge the collections.
        col = MSILCcoly.merge(MSI2Acoly)

        yearImg = col.median()
        nBands = yearImg.bandNames().size()
        yearImg = ee.Image(ee.Algorithms.If(nBands, yearImg, dummyImg))
        return calcNbr(yearImg).set(
            {
                "year": y,
                "system:time_start": startDate.millis(),
                "nBands": nBands,
                "system:date": ee.Date(startDate).format(date_format),
            }
        )

    # Get quarterly median collection.
    def getQuarterlyComp(startDate):
        startDate = ee.Date(startDate)
        endDate = startDate.advance(3, "month")

        # Filter collections and prepare them for merging.
        MSILCcoly = colFilter(MSILCcol, roi, startDate, endDate).map(prepMSI)
        MSI2Acoly = colFilter(MSI2Acol, roi, startDate, endDate).map(prepMSI)

        # Merge the collections.
        col = MSILCcoly.merge(MSI2Acoly)

        yearImg = col.median()
        nBands = yearImg.bandNames().size()
        yearImg = ee.Image(ee.Algorithms.If(nBands, yearImg, dummyImg))
        return calcNbr(yearImg).set(
            {
                "system:time_start": startDate.millis(),
                "nBands": nBands,
                "system:date": ee.Date(startDate).format(date_format),
            }
        )

    # Get monthly median collection.
    def getMonthlyComp(startDate):
        startDate = ee.Date(startDate)
        endDate = startDate.advance(1, "month")

        # Filter collections and prepare them for merging.
        MSILCcoly = colFilter(MSILCcol, roi, startDate, endDate).map(prepMSI)
        MSI2Acoly = colFilter(MSI2Acol, roi, startDate, endDate).map(prepMSI)

        # Merge the collections.
        col = MSILCcoly.merge(MSI2Acoly)

        yearImg = col.median()
        nBands = yearImg.bandNames().size()
        yearImg = ee.Image(ee.Algorithms.If(nBands, yearImg, dummyImg))
        return calcNbr(yearImg).set(
            {
                "system:time_start": startDate.millis(),
                "nBands": nBands,
                "system:date": ee.Date(startDate).format(date_format),
            }
        )

    ################################################################################

    # Make a dummy image for missing years.
    bandNames = ee.List(
        [
            "Blue",
            "Green",
            "Red",
            "Red Edge 1",
            "Red Edge 2",
            "Red Edge 3",
            "NIR",
            "Red Edge 4",
            "SWIR1",
            "SWIR2",
            "QA60",
        ]
    )
    fillerValues = ee.List.repeat(0, bandNames.size())
    dummyImg = ee.Image.constant(fillerValues).rename(bandNames).selfMask().int16()

    # ################################################################################
    # # Get a list of years
    # years = ee.List.sequence(start_year, end_year)

    # ################################################################################
    # # Make list of annual image composites.
    # imgList = years.map(getAnnualComp)

    if frequency == "year":
        years = ee.List.sequence(start_year, end_year)
        imgList = years.map(getAnnualComp)
    elif frequency == "quarter":
        quarters = date_sequence(
            str(start_year) + "-01-01", str(end_year) + "-12-31", "quarter", date_format
        )
        imgList = quarters.map(getQuarterlyComp)
    elif frequency == "month":
        months = date_sequence(
            str(start_year) + "-01-01", str(end_year) + "-12-31", "month", date_format
        )
        imgList = months.map(getMonthlyComp)

    # Convert image composite list to collection
    imgCol = ee.ImageCollection.fromImages(imgList)

    imgCol = imgCol.map(lambda img: img.clip(roi))

    return imgCol


def landsat_timeseries(
    roi=None,
    start_year=1984,
    end_year=None,
    start_date="06-10",
    end_date="09-20",
    apply_fmask=True,
    frequency="year",
    date_format=None,
    step=1,
):
    """Generates an annual Landsat ImageCollection. This algorithm is adapted from https://gist.github.com/jdbcode/76b9ac49faf51627ebd3ff988e10adbc. A huge thank you to Justin Braaten for sharing his fantastic work.

    Args:
        roi (object, optional): Region of interest to create the timelapse. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 1984.
        end_year (int, optional): Ending year for the timelapse. Defaults to None, which means the current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '06-10'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '09-20'.
        apply_fmask (bool, optional): Whether to apply Fmask (Function of mask) for automated clouds, cloud shadows, snow, and water masking.
        frequency (str, optional): Frequency of the timelapse. Defaults to 'year'.
        date_format (str, optional): Format of the date. Defaults to None.
        step (int, optional): The step size to use when creating the date sequence. Defaults to 1.
    Returns:
        object: Returns an ImageCollection containing annual Landsat images.
    """

    # Input and output parameters.
    import re

    if roi is None:
        roi = ee.Geometry.Polygon(
            [
                [
                    [-115.471773, 35.892718],
                    [-115.471773, 36.409454],
                    [-114.271283, 36.409454],
                    [-114.271283, 35.892718],
                    [-115.471773, 35.892718],
                ]
            ],
            None,
            False,
        )

    if end_year is None:
        end_year = get_current_year()

    if not isinstance(roi, ee.Geometry):
        try:
            roi = roi.geometry()
        except Exception as e:
            print("Could not convert the provided roi to ee.Geometry")
            print(e)
            return

    feq_dict = {
        "year": "YYYY",
        "month": "YYYY-MM",
        "quarter": "YYYY-MM",
    }

    if date_format is None:
        date_format = feq_dict[frequency]

    if frequency not in feq_dict:
        raise ValueError("frequency must be year, quarter, or month.")

    # Setup vars to get dates.
    if (
        isinstance(start_year, int)
        and (start_year >= 1984)
        and (start_year < get_current_year())
    ):
        pass
    else:
        print("The start year must be an integer >= 1984.")
        return

    if (
        isinstance(end_year, int)
        and (end_year > 1984)
        and (end_year <= get_current_year())
    ):
        pass
    else:
        print(f"The end year must be an integer <= {get_current_year()}.")
        return

    if re.match(r"[0-9]{2}-[0-9]{2}", start_date) and re.match(
        r"[0-9]{2}-[0-9]{2}", end_date
    ):
        pass
    else:
        print("The start date and end date must be month-day, such as 06-10, 09-20")
        return

    try:
        datetime.datetime(int(start_year), int(start_date[:2]), int(start_date[3:5]))
        datetime.datetime(int(end_year), int(end_date[:2]), int(end_date[3:5]))
    except Exception as e:
        print("The input dates are invalid.")
        raise Exception(e)

    def days_between(d1, d2):
        d1 = datetime.datetime.strptime(d1, "%Y-%m-%d")
        d2 = datetime.datetime.strptime(d2, "%Y-%m-%d")
        return abs((d2 - d1).days)

    n_days = days_between(
        str(start_year) + "-" + start_date, str(start_year) + "-" + end_date
    )
    start_month = int(start_date[:2])
    start_day = int(start_date[3:5])

    # Landsat collection preprocessingEnabled
    # Get Landsat surface reflectance collections for OLI, ETM+ and TM sensors.
    LC09col = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
    LC08col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
    LE07col = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2")
    LT05col = ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")
    LT04col = ee.ImageCollection("LANDSAT/LT04/C02/T1_L2")

    # Define a collection filter by date, bounds, and quality.
    def colFilter(col, roi, start_date, end_date):
        return col.filterBounds(roi).filterDate(start_date, end_date)

    # Function to get and rename bands of interest from OLI.
    def renameOli(img):
        return img.select(
            ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"],
            ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"],
        )

    # Function to get and rename bands of interest from ETM+.
    def renameEtm(img):
        return img.select(
            ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"],
            ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"],
        )

    def fmask(image):
        # see https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2
        # Bit 0 - Fill
        # Bit 1 - Dilated Cloud
        # Bit 2 - Cirrus
        # Bit 3 - Cloud
        # Bit 4 - Cloud Shadow
        qaMask = image.select("QA_PIXEL").bitwiseAnd(int("11111", 2)).eq(0)

        # Apply the scaling factors to the appropriate bands.
        opticalBands = image.select("SR_B.").multiply(0.0000275).add(-0.2)

        # Replace the original bands with the scaled ones and apply the masks.
        return image.addBands(opticalBands, None, True).updateMask(qaMask)

    # Define function to prepare OLI images.
    def prepOli(img):
        orig = img
        if apply_fmask:
            img = fmask(img)
        else:
            img = img.select("SR_B.").multiply(0.0000275).add(-0.2)
        img = renameOli(img)
        return ee.Image(img.copyProperties(orig, orig.propertyNames())).resample(
            "bicubic"
        )

    # Define function to prepare ETM+ images.
    def prepEtm(img):
        orig = img
        if apply_fmask:
            img = fmask(img)
        else:
            img = img.select("SR_B.").multiply(0.0000275).add(-0.2)
        img = renameEtm(img)
        return ee.Image(img.copyProperties(orig, orig.propertyNames())).resample(
            "bicubic"
        )

    # Get annual median collection.
    def getAnnualComp(y):
        startDate = ee.Date.fromYMD(
            ee.Number(y), ee.Number(start_month), ee.Number(start_day)
        )
        endDate = startDate.advance(ee.Number(n_days), "day")

        # Filter collections and prepare them for merging.
        LC09coly = colFilter(LC09col, roi, startDate, endDate).map(prepOli)
        LC08coly = colFilter(LC08col, roi, startDate, endDate).map(prepOli)
        LE07coly = colFilter(LE07col, roi, startDate, endDate).map(prepEtm)
        LT05coly = colFilter(LT05col, roi, startDate, endDate).map(prepEtm)
        LT04coly = colFilter(LT04col, roi, startDate, endDate).map(prepEtm)

        # Merge the collections.
        col = LC09coly.merge(LC08coly).merge(LE07coly).merge(LT05coly).merge(LT04coly)

        yearImg = col.median()
        nBands = yearImg.bandNames().size()
        yearImg = ee.Image(ee.Algorithms.If(nBands, yearImg, dummyImg))
        return yearImg.set(
            {
                "year": y,
                "system:time_start": startDate.millis(),
                "nBands": nBands,
                "system:date": ee.Date(startDate).format(date_format),
            }
        )

    # Get monthly median collection.
    def getMonthlyComp(startDate):
        startDate = ee.Date(startDate)
        endDate = startDate.advance(1, "month")

        # Filter collections and prepare them for merging.
        LC09coly = colFilter(LC09col, roi, startDate, endDate).map(prepOli)
        LC08coly = colFilter(LC08col, roi, startDate, endDate).map(prepOli)
        LE07coly = colFilter(LE07col, roi, startDate, endDate).map(prepEtm)
        LT05coly = colFilter(LT05col, roi, startDate, endDate).map(prepEtm)
        LT04coly = colFilter(LT04col, roi, startDate, endDate).map(prepEtm)

        # Merge the collections.
        col = LC09coly.merge(LC08coly).merge(LE07coly).merge(LT05coly).merge(LT04coly)

        monthImg = col.median()
        nBands = monthImg.bandNames().size()
        monthImg = ee.Image(ee.Algorithms.If(nBands, monthImg, dummyImg))
        return monthImg.set(
            {
                "system:time_start": startDate.millis(),
                "nBands": nBands,
                "system:date": ee.Date(startDate).format(date_format),
            }
        )

    # Get quarterly median collection.
    def getQuarterlyComp(startDate):
        startDate = ee.Date(startDate)

        endDate = startDate.advance(3, "month")

        # Filter collections and prepare them for merging.
        LC09coly = colFilter(LC09col, roi, startDate, endDate).map(prepOli)
        LC08coly = colFilter(LC08col, roi, startDate, endDate).map(prepOli)
        LE07coly = colFilter(LE07col, roi, startDate, endDate).map(prepEtm)
        LT05coly = colFilter(LT05col, roi, startDate, endDate).map(prepEtm)
        LT04coly = colFilter(LT04col, roi, startDate, endDate).map(prepEtm)

        # Merge the collections.
        col = LC09coly.merge(LC08coly).merge(LE07coly).merge(LT05coly).merge(LT04coly)

        quarter = col.median()
        nBands = quarter.bandNames().size()
        quarter = ee.Image(ee.Algorithms.If(nBands, quarter, dummyImg))
        return quarter.set(
            {
                "system:time_start": startDate.millis(),
                "nBands": nBands,
                "system:date": ee.Date(startDate).format(date_format),
            }
        )

    # Make a dummy image for missing years.
    bandNames = ee.List(["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "pixel_qa"])
    fillerValues = ee.List.repeat(0, bandNames.size())
    dummyImg = ee.Image.constant(fillerValues).rename(bandNames).selfMask().int16()

    # Make list of /quarterly/monthly image composites.

    if frequency == "year":
        years = ee.List.sequence(start_year, end_year, step)
        imgList = years.map(getAnnualComp)
    elif frequency == "quarter":
        quarters = date_sequence(
            str(start_year) + "-01-01",
            str(end_year) + "-12-31",
            "quarter",
            date_format,
            step,
        )
        imgList = quarters.map(getQuarterlyComp)
    elif frequency == "month":
        months = date_sequence(
            str(start_year) + "-01-01",
            str(end_year) + "-12-31",
            "month",
            date_format,
            step,
        )
        imgList = months.map(getMonthlyComp)

    # Convert image composite list to collection
    imgCol = ee.ImageCollection.fromImages(imgList)

    imgCol = imgCol.map(
        lambda img: img.clip(roi).set({"coordinates": roi.coordinates()})
    )

    return imgCol


def landsat_timeseries_legacy(
    roi=None,
    start_year=1984,
    end_year=2021,
    start_date="06-10",
    end_date="09-20",
    apply_fmask=True,
    frequency="year",
    date_format=None,
):
    """Generates an annual Landsat ImageCollection. This algorithm is adapted from https://gist.github.com/jdbcode/76b9ac49faf51627ebd3ff988e10adbc. A huge thank you to Justin Braaten for sharing his fantastic work.
    Args:
        roi (object, optional): Region of interest to create the timelapse. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 1984.
        end_year (int, optional): Ending year for the timelapse. Defaults to 2021.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '06-10'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '09-20'.
        apply_fmask (bool, optional): Whether to apply Fmask (Function of mask) for automated clouds, cloud shadows, snow, and water masking.
        frequency (str, optional): Frequency of the timelapse. Defaults to 'year'.
        date_format (str, optional): Format of the date. Defaults to None.
    Returns:
        object: Returns an ImageCollection containing annual Landsat images.
    """

    ################################################################################
    # Input and output parameters.
    import re

    # import datetime

    if roi is None:
        roi = ee.Geometry.Polygon(
            [
                [
                    [-115.471773, 35.892718],
                    [-115.471773, 36.409454],
                    [-114.271283, 36.409454],
                    [-114.271283, 35.892718],
                    [-115.471773, 35.892718],
                ]
            ],
            None,
            False,
        )

    if not isinstance(roi, ee.Geometry):
        try:
            roi = roi.geometry()
        except Exception as e:
            print("Could not convert the provided roi to ee.Geometry")
            print(e)
            return

    feq_dict = {
        "year": "YYYY",
        "month": "YYYY-MM",
        "quarter": "YYYY-MM",
    }

    if date_format is None:
        date_format = feq_dict[frequency]

    if frequency not in feq_dict:
        raise ValueError("frequency must be year, quarter, or month.")

    ################################################################################

    # Setup vars to get dates.
    if isinstance(start_year, int) and (start_year >= 1984) and (start_year < 2021):
        pass
    else:
        print("The start year must be an integer >= 1984.")
        return

    if isinstance(end_year, int) and (end_year > 1984) and (end_year <= 2021):
        pass
    else:
        print("The end year must be an integer <= 2021.")
        return

    if re.match(r"[0-9]{2}-[0-9]{2}", start_date) and re.match(
        r"[0-9]{2}-[0-9]{2}", end_date
    ):
        pass
    else:
        print("The start date and end date must be month-day, such as 06-10, 09-20")
        return

    try:
        datetime.datetime(int(start_year), int(start_date[:2]), int(start_date[3:5]))
        datetime.datetime(int(end_year), int(end_date[:2]), int(end_date[3:5]))
    except Exception as e:
        print("The input dates are invalid.")
        raise Exception(e)

    def days_between(d1, d2):
        d1 = datetime.datetime.strptime(d1, "%Y-%m-%d")
        d2 = datetime.datetime.strptime(d2, "%Y-%m-%d")
        return abs((d2 - d1).days)

    n_days = days_between(
        str(start_year) + "-" + start_date, str(start_year) + "-" + end_date
    )
    start_month = int(start_date[:2])
    start_day = int(start_date[3:5])
    # start_date = str(start_year) + "-" + start_date
    # end_date = str(end_year) + "-" + end_date

    # # Define a collection filter by date, bounds, and quality.
    # def colFilter(col, aoi):  # , startDate, endDate):
    #     return(col.filterBounds(aoi))

    # Landsat collection preprocessingEnabled
    # Get Landsat surface reflectance collections for OLI, ETM+ and TM sensors.
    LC08col = ee.ImageCollection("LANDSAT/LC08/C01/T1_SR")
    LE07col = ee.ImageCollection("LANDSAT/LE07/C01/T1_SR")
    LT05col = ee.ImageCollection("LANDSAT/LT05/C01/T1_SR")
    LT04col = ee.ImageCollection("LANDSAT/LT04/C01/T1_SR")

    # Define a collection filter by date, bounds, and quality.
    def colFilter(col, roi, start_date, end_date):
        return col.filterBounds(roi).filterDate(start_date, end_date)
        # .filter('CLOUD_COVER < 5')
        # .filter('GEOMETRIC_RMSE_MODEL < 15')
        # .filter('IMAGE_QUALITY == 9 || IMAGE_QUALITY_OLI == 9'))

    # Function to get and rename bands of interest from OLI.
    def renameOli(img):
        return img.select(
            ["B2", "B3", "B4", "B5", "B6", "B7", "pixel_qa"],
            ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "pixel_qa"],
        )

    # Function to get and rename bands of interest from ETM+.
    def renameEtm(img):
        return img.select(
            ["B1", "B2", "B3", "B4", "B5", "B7", "pixel_qa"],
            ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "pixel_qa"],
        )

    # Add NBR for LandTrendr segmentation.
    def calcNbr(img):
        return img.addBands(
            img.normalizedDifference(["NIR", "SWIR2"]).multiply(-10000).rename("NBR")
        ).int16()

    # Define function to mask out clouds and cloud shadows in images.
    # Use CFmask band included in USGS Landsat SR image product.
    def fmask(img):
        cloudShadowBitMask = 1 << 3
        cloudsBitMask = 1 << 5
        qa = img.select("pixel_qa")
        mask = (
            qa.bitwiseAnd(cloudShadowBitMask)
            .eq(0)
            .And(qa.bitwiseAnd(cloudsBitMask).eq(0))
        )
        return img.updateMask(mask)

    # Define function to prepare OLI images.
    def prepOli(img):
        orig = img
        img = renameOli(img)
        if apply_fmask:
            img = fmask(img)
        return ee.Image(img.copyProperties(orig, orig.propertyNames())).resample(
            "bicubic"
        )

    # Define function to prepare ETM+ images.
    def prepEtm(img):
        orig = img
        img = renameEtm(img)
        if apply_fmask:
            img = fmask(img)
        return ee.Image(img.copyProperties(orig, orig.propertyNames())).resample(
            "bicubic"
        )

    # Get annual median collection.
    def getAnnualComp(y):
        startDate = ee.Date.fromYMD(
            ee.Number(y), ee.Number(start_month), ee.Number(start_day)
        )
        endDate = startDate.advance(ee.Number(n_days), "day")

        # Filter collections and prepare them for merging.
        LC08coly = colFilter(LC08col, roi, startDate, endDate).map(prepOli)
        LE07coly = colFilter(LE07col, roi, startDate, endDate).map(prepEtm)
        LT05coly = colFilter(LT05col, roi, startDate, endDate).map(prepEtm)
        LT04coly = colFilter(LT04col, roi, startDate, endDate).map(prepEtm)

        # Merge the collections.
        col = LC08coly.merge(LE07coly).merge(LT05coly).merge(LT04coly)

        yearImg = col.median()
        nBands = yearImg.bandNames().size()
        yearImg = ee.Image(ee.Algorithms.If(nBands, yearImg, dummyImg))
        return calcNbr(yearImg).set(
            {
                "year": y,
                "system:time_start": startDate.millis(),
                "nBands": nBands,
                "system:date": ee.Date(startDate).format(date_format),
            }
        )

    # Get monthly median collection.
    def getMonthlyComp(startDate):
        startDate = ee.Date(startDate)
        endDate = startDate.advance(1, "month")

        # Filter collections and prepare them for merging.
        LC08coly = colFilter(LC08col, roi, startDate, endDate).map(prepOli)
        LE07coly = colFilter(LE07col, roi, startDate, endDate).map(prepEtm)
        LT05coly = colFilter(LT05col, roi, startDate, endDate).map(prepEtm)
        LT04coly = colFilter(LT04col, roi, startDate, endDate).map(prepEtm)

        # Merge the collections.
        col = LC08coly.merge(LE07coly).merge(LT05coly).merge(LT04coly)

        monthImg = col.median()
        nBands = monthImg.bandNames().size()
        monthImg = ee.Image(ee.Algorithms.If(nBands, monthImg, dummyImg))
        return calcNbr(monthImg).set(
            {
                "system:time_start": startDate.millis(),
                "nBands": nBands,
                "system:date": ee.Date(startDate).format(date_format),
            }
        )

    # Get quarterly median collection.
    def getQuarterlyComp(startDate):
        startDate = ee.Date(startDate)

        endDate = startDate.advance(3, "month")

        # Filter collections and prepare them for merging.
        LC08coly = colFilter(LC08col, roi, startDate, endDate).map(prepOli)
        LE07coly = colFilter(LE07col, roi, startDate, endDate).map(prepEtm)
        LT05coly = colFilter(LT05col, roi, startDate, endDate).map(prepEtm)
        LT04coly = colFilter(LT04col, roi, startDate, endDate).map(prepEtm)

        # Merge the collections.
        col = LC08coly.merge(LE07coly).merge(LT05coly).merge(LT04coly)

        quarter = col.median()
        nBands = quarter.bandNames().size()
        quarter = ee.Image(ee.Algorithms.If(nBands, quarter, dummyImg))
        return calcNbr(quarter).set(
            {
                "system:time_start": startDate.millis(),
                "nBands": nBands,
                "system:date": ee.Date(startDate).format(date_format),
            }
        )

    ################################################################################

    # Make a dummy image for missing years.
    bandNames = ee.List(["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "pixel_qa"])
    fillerValues = ee.List.repeat(0, bandNames.size())
    dummyImg = ee.Image.constant(fillerValues).rename(bandNames).selfMask().int16()

    # ################################################################################
    # # Get a list of years
    # years = ee.List.sequence(start_year, end_year)

    # ################################################################################
    # # Make list of annual image composites.
    # imgList = years.map(getAnnualComp)

    if frequency == "year":
        years = ee.List.sequence(start_year, end_year)
        imgList = years.map(getAnnualComp)
    elif frequency == "quarter":
        quarters = date_sequence(
            str(start_year) + "-01-01", str(end_year) + "-12-31", "quarter", date_format
        )
        imgList = quarters.map(getQuarterlyComp)
    elif frequency == "month":
        months = date_sequence(
            str(start_year) + "-01-01", str(end_year) + "-12-31", "month", date_format
        )
        imgList = months.map(getMonthlyComp)

    # Convert image composite list to collection
    imgCol = ee.ImageCollection.fromImages(imgList)

    imgCol = imgCol.map(
        lambda img: img.clip(roi).set({"coordinates": roi.coordinates()})
    )

    return imgCol

    # ################################################################################
    # # Run LandTrendr.
    # lt = ee.Algorithms.TemporalSegmentation.LandTrendr(
    #     timeSeries=imgCol.select(['NBR', 'SWIR1', 'NIR', 'Green']),
    #     maxSegments=10,
    #     spikeThreshold=0.7,
    #     vertexCountOvershoot=3,
    #     preventOneYearRecovery=True,
    #     recoveryThreshold=0.5,
    #     pvalThreshold=0.05,
    #     bestModelProportion=0.75,
    #     minObservationsNeeded=6)

    # ################################################################################
    # # Get fitted imagery. This starts export tasks.
    # def getYearStr(year):
    #     return(ee.String('yr_').cat(ee.Algorithms.String(year).slice(0,4)))

    # yearsStr = years.map(getYearStr)

    # r = lt.select(['SWIR1_fit']).arrayFlatten([yearsStr]).toShort()
    # g = lt.select(['NIR_fit']).arrayFlatten([yearsStr]).toShort()
    # b = lt.select(['Green_fit']).arrayFlatten([yearsStr]).toShort()

    # for i, c in zip([r, g, b], ['r', 'g', 'b']):
    #     descr = 'mamore-river-'+c
    #     name = 'users/user/'+descr
    #     print(name)
    #     task = ee.batch.Export.image.toAsset(
    #     image=i,
    #     region=roi.getInfo()['coordinates'],
    #     assetId=name,
    #     description=descr,
    #     scale=30,
    #     crs='EPSG:3857',
    #     maxPixels=1e13)
    #     task.start()


def modis_timeseries(
    asset_id="MODIS/006/MOD13A2",
    band_name=None,
    roi=None,
    start_year=2001,
    end_year=None,
    start_date="01-01",
    end_date="12-31",
):
    """Generates a Monthly MODIS ImageCollection.
    Args:
        asset_id (str, optional): The asset id the MODIS ImageCollection.
        band_name (str, optional): The band name of the image to use.
        roi (object, optional): Region of interest to create the timelapse. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 1984.
        end_year (int, optional): Ending year for the timelapse. Defaults to None, which is the current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '06-10'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '09-20'.
    Returns:
        object: Returns an ImageCollection containing month MODIS images.
    """

    try:
        if end_year is None:
            end_year = datetime.datetime.now().year

        collection = ee.ImageCollection(asset_id)
        if band_name is None:
            band_name = collection.first().bandNames().getInfo()[0]
        collection = collection.select(band_name)
        if roi is not None:
            if isinstance(roi, ee.Geometry):
                collection = ee.ImageCollection(
                    collection.map(lambda img: img.clip(roi))
                )
            elif isinstance(roi, ee.FeatureCollection):
                collection = ee.ImageCollection(
                    collection.map(lambda img: img.clipToCollection(roi))
                )

        start = str(start_year) + "-" + start_date
        end = str(end_year) + "-" + end_date

        seq = date_sequence(start, end, "month")

        def monthly_modis(start_d):
            end_d = ee.Date(start_d).advance(1, "month")
            return ee.Image(collection.filterDate(start_d, end_d).mean())

        images = ee.ImageCollection(seq.map(monthly_modis))
        return images

    except Exception as e:
        raise Exception(e)


def landsat_timelapse(
    roi=None,
    out_gif=None,
    start_year=1984,
    end_year=None,
    start_date="06-10",
    end_date="09-20",
    bands=["NIR", "Red", "Green"],
    vis_params=None,
    dimensions=768,
    frames_per_second=5,
    crs="EPSG:3857",
    apply_fmask=True,
    nd_bands=None,
    nd_threshold=0,
    nd_palette=["black", "blue"],
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    frequency="year",
    date_format=None,
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    loop=0,
    mp4=False,
    fading=False,
    step=1,
):
    """Generates a Landsat timelapse GIF image. This function is adapted from https://emaprlab.users.earthengine.app/view/lt-gee-time-series-animator. A huge thank you to Justin Braaten for sharing his fantastic work.

    Args:
        roi (object, optional): Region of interest to create the timelapse. Defaults to None.
        out_gif (str, optional): File path to the output animated GIF. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 1984.
        end_year (int, optional): Ending year for the timelapse. Defaults to None, which will use the current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '06-10'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '09-20'.
        bands (list, optional): Three bands selected from ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2', 'pixel_qa']. Defaults to ['NIR', 'Red', 'Green'].
        vis_params (dict, optional): Visualization parameters. Defaults to None.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 5.
        crs (str, optional): The coordinate reference system to use. Defaults to "EPSG:3857".
        apply_fmask (bool, optional): Whether to apply Fmask (Function of mask) for automated clouds, cloud shadows, snow, and water masking.
        nd_bands (list, optional): A list of names specifying the bands to use, e.g., ['Green', 'SWIR1']. The normalized difference is computed as (first − second) / (first + second). Note that negative input values are forced to 0 so that the result is confined to the range (-1, 1).
        nd_threshold (float, optional): The threshold for extracting pixels from the normalized difference band.
        nd_palette (list, optional): The color palette to use for displaying the normalized difference band.
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Line width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        frequency (str, optional): Frequency of the timelapse. Defaults to 'year'.
        date_format (str, optional): Date format for the timelapse. Defaults to None.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Lower left corner of the title. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        add_text (bool, optional): Whether to add animated text to the timelapse. Defaults to True.
        title_xy (tuple, optional): Lower left corner of the text sequency. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        loop (int, optional): Controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        mp4 (bool, optional): Whether to convert the GIF to MP4. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).
        step (int, optional): Step size for the timelapse. Defaults to 1.

    Returns:
        str: File path to the output GIF image.
    """

    if roi is None:
        roi = ee.Geometry.Polygon(
            [
                [
                    [-115.471773, 35.892718],
                    [-115.471773, 36.409454],
                    [-114.271283, 36.409454],
                    [-114.271283, 35.892718],
                    [-115.471773, 35.892718],
                ]
            ],
            None,
            False,
        )
    elif isinstance(roi, ee.Feature) or isinstance(roi, ee.FeatureCollection):
        roi = roi.geometry()
    elif isinstance(roi, ee.Geometry):
        pass
    else:
        raise ValueError("The provided roi is invalid. It must be an ee.Geometry")

    if out_gif is None:
        out_gif = temp_file_path(".gif")
    elif not out_gif.endswith(".gif"):
        raise ValueError("The output file must end with .gif")
    else:
        out_gif = os.path.abspath(out_gif)
    out_dir = os.path.dirname(out_gif)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    if end_year is None:
        end_year = get_current_year()

    allowed_bands = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "pixel_qa"]

    if len(bands) == 3 and all(x in allowed_bands for x in bands):
        pass
    else:
        raise Exception(
            "You can only select 3 bands from the following: {}".format(
                ", ".join(allowed_bands)
            )
        )

    if nd_bands is not None:
        if len(nd_bands) == 2 and all(x in allowed_bands[:-1] for x in nd_bands):
            pass
        else:
            raise Exception(
                "You can only select two bands from the following: {}".format(
                    ", ".join(allowed_bands[:-1])
                )
            )

    try:
        if vis_params is None:
            vis_params = {}
            vis_params["bands"] = bands
            vis_params["min"] = 0
            vis_params["max"] = 0.4
            vis_params["gamma"] = [1, 1, 1]
        raw_col = landsat_timeseries(
            roi,
            start_year,
            end_year,
            start_date,
            end_date,
            apply_fmask,
            frequency,
            date_format,
            step,
        )

        col = raw_col.select(bands).map(
            lambda img: img.visualize(**vis_params).set(
                {
                    "system:time_start": img.get("system:time_start"),
                    "system:date": img.get("system:date"),
                }
            )
        )
        if overlay_data is not None:
            col = add_overlay(
                col, overlay_data, overlay_color, overlay_width, overlay_opacity
            )

        if (
            isinstance(dimensions, int)
            and dimensions > 768
            or isinstance(dimensions, str)
            and any(dim > 768 for dim in list(map(int, dimensions.split("x"))))
        ):
            count = col.size().getInfo()
            basename = os.path.basename(out_gif)[:-4]
            names = [
                os.path.join(
                    out_dir, f"{basename}_{str(i+1).zfill(int(len(str(count))))}.jpg"
                )
                for i in range(count)
            ]
            get_image_collection_thumbnails(
                col,
                out_dir,
                vis_params={
                    "min": 0,
                    "max": 255,
                    "bands": ["vis-red", "vis-green", "vis-blue"],
                },
                dimensions=dimensions,
                names=names,
            )
            make_gif(
                names,
                out_gif,
                fps=frames_per_second,
                loop=loop,
                mp4=False,
                clean_up=True,
            )

        else:
            video_args = vis_params.copy()
            video_args["dimensions"] = dimensions
            video_args["region"] = roi
            video_args["framesPerSecond"] = frames_per_second
            video_args["crs"] = crs
            video_args["bands"] = ["vis-red", "vis-green", "vis-blue"]
            video_args["min"] = 0
            video_args["max"] = 255

            download_ee_video(col, video_args, out_gif)

        if os.path.exists(out_gif):
            if title is not None and isinstance(title, str):
                add_text_to_gif(
                    out_gif,
                    out_gif,
                    xy=title_xy,
                    text_sequence=title,
                    font_type=font_type,
                    font_size=font_size,
                    font_color=font_color,
                    add_progress_bar=add_progress_bar,
                    progress_bar_color=progress_bar_color,
                    progress_bar_height=progress_bar_height,
                    duration=1000 / frames_per_second,
                    loop=loop,
                )
            if add_text:
                if text_sequence is None:
                    text_sequence = col.aggregate_array("system:date").getInfo()
                add_text_to_gif(
                    out_gif,
                    out_gif,
                    xy=text_xy,
                    text_sequence=text_sequence,
                    font_type=font_type,
                    font_size=font_size,
                    font_color=font_color,
                    add_progress_bar=add_progress_bar,
                    progress_bar_color=progress_bar_color,
                    progress_bar_height=progress_bar_height,
                    duration=1000 / frames_per_second,
                    loop=loop,
                )

        if nd_bands is not None:
            nd_images = landsat_ts_norm_diff(
                raw_col, bands=nd_bands, threshold=nd_threshold
            )
            out_nd_gif = out_gif.replace(".gif", "_nd.gif")
            landsat_ts_norm_diff_gif(
                nd_images,
                out_gif=out_nd_gif,
                vis_params=None,
                palette=nd_palette,
                dimensions=dimensions,
                frames_per_second=frames_per_second,
            )

        if os.path.exists(out_gif):
            reduce_gif_size(out_gif)

        if isinstance(fading, bool):
            fading = int(fading)
        if fading > 0:
            gif_fading(out_gif, out_gif, duration=fading, verbose=False)

        if mp4:
            out_mp4 = out_gif.replace(".gif", ".mp4")
            gif_to_mp4(out_gif, out_mp4)

        return out_gif

    except Exception as e:
        raise Exception(e)


def landsat_timelapse_legacy(
    roi=None,
    out_gif=None,
    start_year=1984,
    end_year=None,
    start_date="06-10",
    end_date="09-20",
    bands=["NIR", "Red", "Green"],
    vis_params=None,
    dimensions=768,
    frames_per_second=5,
    crs="EPSG:3857",
    apply_fmask=True,
    nd_bands=None,
    nd_threshold=0,
    nd_palette=["black", "blue"],
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    frequency="year",
    date_format=None,
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    loop=0,
    mp4=False,
    fading=False,
):
    """Generates a Landsat timelapse GIF image. This function is adapted from https://emaprlab.users.earthengine.app/view/lt-gee-time-series-animator. A huge thank you to Justin Braaten for sharing his fantastic work.

    Args:
        roi (object, optional): Region of interest to create the timelapse. Defaults to None.
        out_gif (str, optional): File path to the output animated GIF. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 1984.
        end_year (int, optional): Ending year for the timelapse. Defaults to None, which means the current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '06-10'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '09-20'.
        bands (list, optional): Three bands selected from ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2', 'pixel_qa']. Defaults to ['NIR', 'Red', 'Green'].
        vis_params (dict, optional): Visualization parameters. Defaults to None.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 5.
        crs (str, optional): The coordinate reference system to use. Defaults to "EPSG:3857".
        apply_fmask (bool, optional): Whether to apply Fmask (Function of mask) for automated clouds, cloud shadows, snow, and water masking.
        nd_bands (list, optional): A list of names specifying the bands to use, e.g., ['Green', 'SWIR1']. The normalized difference is computed as (first − second) / (first + second). Note that negative input values are forced to 0 so that the result is confined to the range (-1, 1).
        nd_threshold (float, optional): The threshold for extracting pixels from the normalized difference band.
        nd_palette (list, optional): The color palette to use for displaying the normalized difference band.
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Line width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        frequency (str, optional): Frequency of the timelapse. Defaults to 'year'.
        date_format (str, optional): Date format for the timelapse. Defaults to None.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Lower left corner of the title. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        add_text (bool, optional): Whether to add animated text to the timelapse. Defaults to True.
        title_xy (tuple, optional): Lower left corner of the text sequency. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        loop (int, optional): Controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        mp4 (bool, optional): Whether to convert the GIF to MP4. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).

    Returns:
        str: File path to the output GIF image.
    """

    if end_year is None:
        end_year = get_current_year()

    if roi is None:
        roi = ee.Geometry.Polygon(
            [
                [
                    [-115.471773, 35.892718],
                    [-115.471773, 36.409454],
                    [-114.271283, 36.409454],
                    [-114.271283, 35.892718],
                    [-115.471773, 35.892718],
                ]
            ],
            None,
            False,
        )
    elif isinstance(roi, ee.Feature) or isinstance(roi, ee.FeatureCollection):
        roi = roi.geometry()
    elif isinstance(roi, ee.Geometry):
        pass
    else:
        raise ValueError("The provided roi is invalid. It must be an ee.Geometry")

    if out_gif is None:
        out_gif = temp_file_path(".gif")
    elif not out_gif.endswith(".gif"):
        raise ValueError("The output file must end with .gif")
    else:
        out_gif = os.path.abspath(out_gif)
    out_dir = os.path.dirname(out_gif)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    allowed_bands = ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2", "pixel_qa"]

    if len(bands) == 3 and all(x in allowed_bands for x in bands):
        pass
    else:
        raise Exception(
            "You can only select 3 bands from the following: {}".format(
                ", ".join(allowed_bands)
            )
        )

    if nd_bands is not None:
        if len(nd_bands) == 2 and all(x in allowed_bands[:-1] for x in nd_bands):
            pass
        else:
            raise Exception(
                "You can only select two bands from the following: {}".format(
                    ", ".join(allowed_bands[:-1])
                )
            )

    try:
        if vis_params is None:
            vis_params = {}
            vis_params["bands"] = bands
            vis_params["min"] = 0
            vis_params["max"] = 4000
            vis_params["gamma"] = [1, 1, 1]
        raw_col = landsat_timeseries(
            roi,
            start_year,
            end_year,
            start_date,
            end_date,
            apply_fmask,
            frequency,
            date_format,
        )

        col = raw_col.select(bands).map(
            lambda img: img.visualize(**vis_params).set(
                {
                    "system:time_start": img.get("system:time_start"),
                    "system:date": img.get("system:date"),
                }
            )
        )
        if overlay_data is not None:
            col = add_overlay(
                col, overlay_data, overlay_color, overlay_width, overlay_opacity
            )

        if (
            isinstance(dimensions, int)
            and dimensions > 768
            or isinstance(dimensions, str)
            and any(dim > 768 for dim in list(map(int, dimensions.split("x"))))
        ):
            count = col.size().getInfo()
            basename = os.path.basename(out_gif)[:-4]
            names = [
                os.path.join(
                    out_dir, f"{basename}_{str(i+1).zfill(int(len(str(count))))}.jpg"
                )
                for i in range(count)
            ]
            get_image_collection_thumbnails(
                col,
                out_dir,
                vis_params={
                    "min": 0,
                    "max": 255,
                    "bands": ["vis-red", "vis-green", "vis-blue"],
                },
                dimensions=dimensions,
                names=names,
            )
            make_gif(
                names,
                out_gif,
                fps=frames_per_second,
                loop=loop,
                mp4=False,
                clean_up=True,
            )

        else:
            video_args = vis_params.copy()
            video_args["dimensions"] = dimensions
            video_args["region"] = roi
            video_args["framesPerSecond"] = frames_per_second
            video_args["crs"] = crs
            video_args["bands"] = ["vis-red", "vis-green", "vis-blue"]
            video_args["min"] = 0
            video_args["max"] = 255

            download_ee_video(col, video_args, out_gif)

        if os.path.exists(out_gif):
            if title is not None and isinstance(title, str):
                add_text_to_gif(
                    out_gif,
                    out_gif,
                    xy=title_xy,
                    text_sequence=title,
                    font_type=font_type,
                    font_size=font_size,
                    font_color=font_color,
                    add_progress_bar=add_progress_bar,
                    progress_bar_color=progress_bar_color,
                    progress_bar_height=progress_bar_height,
                    duration=1000 / frames_per_second,
                    loop=loop,
                )
            if add_text:
                if text_sequence is None:
                    text_sequence = col.aggregate_array("system:date").getInfo()
                add_text_to_gif(
                    out_gif,
                    out_gif,
                    xy=text_xy,
                    text_sequence=text_sequence,
                    font_type=font_type,
                    font_size=font_size,
                    font_color=font_color,
                    add_progress_bar=add_progress_bar,
                    progress_bar_color=progress_bar_color,
                    progress_bar_height=progress_bar_height,
                    duration=1000 / frames_per_second,
                    loop=loop,
                )

        if nd_bands is not None:
            nd_images = landsat_ts_norm_diff(
                raw_col, bands=nd_bands, threshold=nd_threshold
            )
            out_nd_gif = out_gif.replace(".gif", "_nd.gif")
            landsat_ts_norm_diff_gif(
                nd_images,
                out_gif=out_nd_gif,
                vis_params=None,
                palette=nd_palette,
                dimensions=dimensions,
                frames_per_second=frames_per_second,
            )

        if os.path.exists(out_gif):
            reduce_gif_size(out_gif)

        if isinstance(fading, bool):
            fading = int(fading)
        if fading > 0:
            gif_fading(out_gif, out_gif, duration=fading, verbose=False)

        if mp4:
            out_mp4 = out_gif.replace(".gif", ".mp4")
            gif_to_mp4(out_gif, out_mp4)

        return out_gif

    except Exception as e:
        raise Exception(e)


def sentinel1_timelapse_legacy(
    roi=None,
    out_gif=None,
    start_year=2015,
    end_year=None,
    start_date="01-01",
    end_date="12-31",
    vis_params=None,
    dimensions=768,
    frames_per_second=5,
    crs="EPSG:3857",
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    frequency="year",
    orbit=["ascending", "descending"],
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    loop=0,
    mp4=False,
    fading=False,
):
    """Generates a Sentinel-1 timelapse animated GIF or MP4.

    Args:
        roi (object, optional): Region of interest to create the timelapse. Defaults to LV & Lake Mead.
        out_gif (str, optional): File path to the output animated GIF. Defaults to the Downloads folder s1_ts_*.gif.
        start_year (int, optional): Starting year for the timelapse. Defaults to 2015.
        end_year (int, optional): Ending year for the timelapse. Defaults to current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '01-01'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '12-31'.
        vis_params (dict, optional): Visualization parameters. Defaults to {'min':-18, 'max': -4}.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 5.
        crs (str, optional): Coordinate reference system. Defaults to 'EPSG:3857'.
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Line width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        frequency (str, optional): Frequency of the timelapse. Defaults to 'year'. Can be year, quarter or month.
        orbit (list, optional): List of orbit directions to include. Can be ['ascending'], ['descending'], or ['ascending', 'descending']. Defaults to both.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Lower left corner of the title. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        add_text (bool, optional): Whether to add animated text to the timelapse. Defaults to True.
        title_xy (tuple, optional): Lower left corner of the text sequency. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to image start dates.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to 'white'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        loop (int, optional): Controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        mp4 (bool, optional): Whether to convert the GIF to MP4. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).

    Returns:
        str: File path to the output GIF image.
    """

    CURRENT_YEAR, ROI_DEFAULT = sentinel1_defaults()
    roi = roi or ROI_DEFAULT
    end_year = end_year or CURRENT_YEAR

    col = sentinel1_timeseries(
        roi=roi,
        start_year=start_year,
        end_year=end_year,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        orbit=orbit,
        clip=True,
    )

    vis_params = vis_params or {"min": -25, "max": 5}

    if out_gif is None:
        out_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        filename = "s1_ts_" + random_string() + ".gif"
        out_gif = os.path.join(out_dir, filename)
    elif not out_gif.endswith(".gif"):
        print("The output file must end with .gif")
        return
    else:
        out_gif = os.path.abspath(out_gif)
        out_dir = os.path.dirname(out_gif)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    if overlay_data is not None:
        col = add_overlay(
            col, overlay_data, overlay_color, overlay_width, overlay_opacity
        )

    if (
        isinstance(dimensions, int)
        and dimensions > 768
        or isinstance(dimensions, str)
        and any(dim > 768 for dim in list(map(int, dimensions.split("x"))))
    ):
        count = col.size().getInfo()
        basename = os.path.basename(out_gif)[:-4]
        names = [
            os.path.join(
                out_dir, f"{basename}_{str(i+1).zfill(int(len(str(count))))}.jpg"
            )
            for i in range(count)
        ]
        get_image_collection_thumbnails(
            col,
            out_dir,
            vis_params=vis_params,
            dimensions=dimensions,
            names=names,
        )
        make_gif(
            names,
            out_gif,
            fps=frames_per_second,
            loop=loop,
            mp4=False,
            clean_up=True,
        )
    else:
        video_args = vis_params.copy()
        video_args["dimensions"] = dimensions
        video_args["region"] = roi
        video_args["framesPerSecond"] = frames_per_second
        video_args["crs"] = crs
        video_args["min"] = vis_params["min"]
        video_args["max"] = vis_params["max"]

        download_ee_video(col, video_args, out_gif)

    if os.path.exists(out_gif):
        if title is not None and isinstance(title, str):
            add_text_to_gif(
                out_gif,
                out_gif,
                xy=title_xy,
                text_sequence=title,
                font_type=font_type,
                font_size=font_size,
                font_color=font_color,
                add_progress_bar=add_progress_bar,
                progress_bar_color=progress_bar_color,
                progress_bar_height=progress_bar_height,
                duration=1000 / frames_per_second,
                loop=loop,
            )
        if add_text:
            if text_sequence is None:
                text_sequence = col.aggregate_array("system:date").getInfo()
            add_text_to_gif(
                out_gif,
                out_gif,
                xy=text_xy,
                text_sequence=text_sequence,
                font_type=font_type,
                font_size=font_size,
                font_color=font_color,
                add_progress_bar=add_progress_bar,
                progress_bar_color=progress_bar_color,
                progress_bar_height=progress_bar_height,
                duration=1000 / frames_per_second,
                loop=loop,
            )
        if os.path.exists(out_gif):
            reduce_gif_size(out_gif)
        if isinstance(fading, bool):
            fading = int(fading)
        if fading > 0:
            gif_fading(out_gif, out_gif, duration=fading, verbose=False)
        if mp4:
            out_mp4 = out_gif.replace(".gif", ".mp4")
            gif_to_mp4(out_gif, out_mp4)

    return out_gif


def sentinel2_timelapse(
    roi=None,
    out_gif=None,
    start_year=2015,
    end_year=None,
    start_date="06-10",
    end_date="09-20",
    bands=["NIR", "Red", "Green"],
    vis_params=None,
    dimensions=768,
    frames_per_second=5,
    crs="EPSG:3857",
    apply_fmask=True,
    cloud_pct=30,
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    frequency="year",
    date_format=None,
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    loop=0,
    mp4=False,
    fading=False,
    step=1,
    **kwargs,
):
    """Generates a Sentinel-2 timelapse GIF image. This function is adapted from https://emaprlab.users.earthengine.app/view/lt-gee-time-series-animator. A huge thank you to Justin Braaten for sharing his fantastic work.

    Args:
        roi (object, optional): Region of interest to create the timelapse. Defaults to None.
        out_gif (str, optional): File path to the output animated GIF. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 2015.
        end_year (int, optional): Ending year for the timelapse. Defaults to None, which means the current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '06-10'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '09-20'.
        bands (list, optional): Three bands selected from ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2', 'Red Edge 1', 'Red Edge 2', 'Red Edge 3', 'Red Edge 4']. Defaults to ['NIR', 'Red', 'Green'].
        vis_params (dict, optional): Visualization parameters. Defaults to None.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        crs (str, optional): Coordinate reference system. Defaults to 'EPSG:3857'.
        apply_fmask (bool, optional): Whether to apply Fmask (Function of mask) for automated clouds, cloud shadows, snow, and water masking.
        cloud_pct (int, optional): Maximum percentage of cloud coverage allowed. Defaults to 30.
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Line width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        frequency (str, optional): Frequency of the timelapse. Defaults to 'year'.
        date_format (str, optional): Date format for the timelapse. Defaults to None.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Lower left corner of the title. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        add_text (bool, optional): Whether to add animated text to the timelapse. Defaults to True.
        title_xy (tuple, optional): Lower left corner of the text sequency. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        loop (int, optional): Controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        mp4 (bool, optional): Whether to convert the GIF to MP4. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).
        step (int, optional): Step size for selecting images. Defaults to 1.
        kwargs (optional): Additional arguments to pass the geemap.create_timeseries() function.

    Returns:
        str: File path to the output GIF image.
    """

    if end_year is None:
        end_year = datetime.datetime.now().year

    if roi is None:
        roi = ee.Geometry.Polygon(
            [
                [
                    [-115.471773, 35.892718],
                    [-115.471773, 36.409454],
                    [-114.271283, 36.409454],
                    [-114.271283, 35.892718],
                    [-115.471773, 35.892718],
                ]
            ],
            None,
            False,
        )
    elif isinstance(roi, ee.Feature) or isinstance(roi, ee.FeatureCollection):
        roi = roi.geometry()
    elif isinstance(roi, ee.Geometry):
        pass
    else:
        print("The provided roi is invalid. It must be an ee.Geometry")
        return

    if out_gif is None:
        out_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        filename = "s2_ts_" + random_string() + ".gif"
        out_gif = os.path.join(out_dir, filename)
    elif not out_gif.endswith(".gif"):
        print("The output file must end with .gif")
        return
    else:
        out_gif = os.path.abspath(out_gif)
        out_dir = os.path.dirname(out_gif)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    allowed_bands = {
        "Blue": "B2",
        "Green": "B3",
        "Red": "B4",
        "Red Edge 1": "B5",
        "Red Edge 2": "B6",
        "Red Edge 3": "B7",
        "NIR": "B8",
        "Red Edge 4": "B8A",
        "SWIR1": "B11",
        "SWIR2": "B12",
        "QA60": "QA60",
    }

    if bands is None:
        bands = ["SWIR1", "NIR", "Red"]

    for index, band in enumerate(bands):
        if band in allowed_bands:
            bands[index] = allowed_bands[band]

    if len(bands) == 3:
        pass
    else:
        raise Exception(
            "You can only select 3 bands from the following: {}".format(
                ", ".join(allowed_bands)
            )
        )

    try:
        if vis_params is None:
            vis_params = {}
            vis_params["bands"] = bands
            vis_params["min"] = 0
            vis_params["max"] = 0.4
            vis_params["gamma"] = [1, 1, 1]

        if "reducer" not in kwargs:
            kwargs["reducer"] = "median"
        if "drop_empty" not in kwargs:
            kwargs["drop_empty"] = True
        if "parallel_scale" not in kwargs:
            kwargs["parallel_scale"] = 1
        kwargs["date_format"] = date_format
        col = sentinel2_timeseries(
            roi,
            start_year,
            end_year,
            start_date,
            end_date,
            bands,
            apply_fmask,
            cloud_pct,
            frequency,
            step=step,
            **kwargs,
        )
        col = col.select(bands).map(
            lambda img: img.visualize(**vis_params).set(
                {
                    "system:time_start": img.get("system:time_start"),
                    "system:date": img.get("system:date"),
                }
            )
        )
        if overlay_data is not None:
            col = add_overlay(
                col, overlay_data, overlay_color, overlay_width, overlay_opacity
            )

        if (
            isinstance(dimensions, int)
            and dimensions > 768
            or isinstance(dimensions, str)
            and any(dim > 768 for dim in list(map(int, dimensions.split("x"))))
        ):
            count = col.size().getInfo()
            basename = os.path.basename(out_gif)[:-4]
            names = [
                os.path.join(
                    out_dir, f"{basename}_{str(i+1).zfill(int(len(str(count))))}.jpg"
                )
                for i in range(count)
            ]
            get_image_collection_thumbnails(
                col,
                out_dir,
                vis_params={
                    "min": 0,
                    "max": 255,
                    "bands": ["vis-red", "vis-green", "vis-blue"],
                },
                dimensions=dimensions,
                names=names,
            )
            make_gif(
                names,
                out_gif,
                fps=frames_per_second,
                loop=loop,
                mp4=False,
                clean_up=True,
            )
        else:
            video_args = vis_params.copy()
            video_args["dimensions"] = dimensions
            video_args["region"] = roi
            video_args["framesPerSecond"] = frames_per_second
            video_args["crs"] = crs
            video_args["bands"] = ["vis-red", "vis-green", "vis-blue"]
            video_args["min"] = 0
            video_args["max"] = 255

            download_ee_video(col, video_args, out_gif)

        if os.path.exists(out_gif):
            if title is not None and isinstance(title, str):
                add_text_to_gif(
                    out_gif,
                    out_gif,
                    xy=title_xy,
                    text_sequence=title,
                    font_type=font_type,
                    font_size=font_size,
                    font_color=font_color,
                    add_progress_bar=add_progress_bar,
                    progress_bar_color=progress_bar_color,
                    progress_bar_height=progress_bar_height,
                    duration=1000 / frames_per_second,
                    loop=loop,
                )
            if add_text:
                if text_sequence is None:
                    text_sequence = col.aggregate_array("system:date").getInfo()
                add_text_to_gif(
                    out_gif,
                    out_gif,
                    xy=text_xy,
                    text_sequence=text_sequence,
                    font_type=font_type,
                    font_size=font_size,
                    font_color=font_color,
                    add_progress_bar=add_progress_bar,
                    progress_bar_color=progress_bar_color,
                    progress_bar_height=progress_bar_height,
                    duration=1000 / frames_per_second,
                    loop=loop,
                )

        if os.path.exists(out_gif):
            reduce_gif_size(out_gif)

        if isinstance(fading, bool):
            fading = int(fading)
        if fading > 0:
            gif_fading(out_gif, out_gif, duration=fading, verbose=False)

        if mp4:
            out_mp4 = out_gif.replace(".gif", ".mp4")
            gif_to_mp4(out_gif, out_mp4)

        return out_gif

    except Exception as e:
        print(e)


def landsat_ts_norm_diff(collection, bands=["Green", "SWIR1"], threshold=0):
    """Computes a normalized difference index based on a Landsat timeseries.

    Args:
        collection (ee.ImageCollection): A Landsat timeseries.
        bands (list, optional): The bands to use for computing normalized difference. Defaults to ['Green', 'SWIR1'].
        threshold (float, optional): The threshold to extract features. Defaults to 0.

    Returns:
        ee.ImageCollection: An ImageCollection containing images with values greater than the specified threshold.
    """
    nd_images = collection.map(
        lambda img: img.normalizedDifference(bands)
        .gt(threshold)
        .copyProperties(img, img.propertyNames())
    )
    return nd_images


def landsat_ts_norm_diff_gif(
    collection,
    out_gif=None,
    vis_params=None,
    palette=["black", "blue"],
    dimensions=768,
    frames_per_second=10,
    mp4=False,
):
    """[summary]

    Args:
        collection (ee.ImageCollection): The normalized difference Landsat timeseires.
        out_gif (str, optional): File path to the output animated GIF. Defaults to None.
        vis_params (dict, optional): Visualization parameters. Defaults to None.
        palette (list, optional): The palette to use for visualizing the timelapse. Defaults to ['black', 'blue']. The first color in the list is the background color.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        mp4 (bool, optional): If True, the output gif will be converted to mp4. Defaults to False.

    Returns:
        str: File path to the output animated GIF.
    """
    coordinates = ee.Image(collection.first()).get("coordinates")
    roi = ee.Geometry.Polygon(coordinates, None, False)

    if out_gif is None:
        out_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        filename = "landsat_ts_nd_" + random_string() + ".gif"
        out_gif = os.path.join(out_dir, filename)
    elif not out_gif.endswith(".gif"):
        raise Exception("The output file must end with .gif")

    bands = ["nd"]
    if vis_params is None:
        vis_params = {}
        vis_params["bands"] = bands
        vis_params["palette"] = palette

    video_args = vis_params.copy()
    video_args["dimensions"] = dimensions
    video_args["region"] = roi
    video_args["framesPerSecond"] = frames_per_second
    video_args["crs"] = "EPSG:3857"

    if "bands" not in video_args.keys():
        video_args["bands"] = bands

    download_ee_video(collection, video_args, out_gif)

    if os.path.exists(out_gif):
        reduce_gif_size(out_gif)

    if mp4:
        out_mp4 = out_gif.replace(".gif", ".mp4")
        gif_to_mp4(out_gif, out_mp4)


def goes_timeseries(
    start_date="2021-10-24T14:00:00",
    end_date="2021-10-25T01:00:00",
    data="GOES-17",
    scan="full_disk",
    region=None,
    show_night=[False, "a_mode"],
):
    """Create a time series of GOES data. The code is adapted from Justin Braaten's code: https://code.earthengine.google.com/57245f2d3d04233765c42fb5ef19c1f4.
    Credits to Justin Braaten. See also https://jstnbraaten.medium.com/goes-in-earth-engine-53fbc8783c16

    Args:
        start_date (str, optional): The start date of the time series. Defaults to "2021-10-24T14:00:00".
        end_date (str, optional): The end date of the time series. Defaults to "2021-10-25T01:00:00".
        data (str, optional): The GOES satellite data to use. Defaults to "GOES-17".
        scan (str, optional): The GOES scan to use. Defaults to "full_disk".
        region (ee.Geometry, optional): The region of interest. Defaults to None.
        show_night (list, optional): Show the clouds at night through [True, "a_mode"] o [True, "b_mode"].  Defaults to [False, "a_mode"]
    Raises:
        ValueError: The data must be either GOES-16 or GOES-17.
        ValueError: The scan must be either full_disk, conus, or mesoscale.

    Returns:
        ee.ImageCollection: GOES timeseries.
    """

    if data not in ["GOES-16", "GOES-17"]:
        raise ValueError("The data must be either GOES-16 or GOES-17.")

    if scan.lower() not in ["full_disk", "conus", "mesoscale"]:
        raise ValueError("The scan must be either full_disk, conus, or mesoscale.")

    scan_types = {
        "full_disk": "MCMIPF",
        "conus": "MCMIPC",
        "mesoscale": "MCMIPM",
    }

    col = ee.ImageCollection(f"NOAA/GOES/{data[-2:]}/{scan_types[scan.lower()]}")

    if region is None:
        region = ee.Geometry.Polygon(
            [
                [
                    [-159.5954379282731, 60.40883060191719],
                    [-159.5954379282731, 24.517881970830725],
                    [-114.2438754282731, 24.517881970830725],
                    [-114.2438754282731, 60.40883060191719],
                ]
            ],
            None,
            False,
        )

    # Applies scaling factors.
    def applyScaleAndOffset(img):
        def getFactorImg(factorNames):
            factorList = img.toDictionary().select(factorNames).values()
            return ee.Image.constant(factorList)

        scaleImg = getFactorImg(["CMI_C.._scale"])
        offsetImg = getFactorImg(["CMI_C.._offset"])
        scaled = img.select("CMI_C..").multiply(scaleImg).add(offsetImg)
        return img.addBands(**{"srcImg": scaled, "overwrite": True})

    # Adds a synthetic green band.
    def addGreenBand(img):
        green = img.expression(
            "CMI_GREEN = 0.45 * red + 0.10 * nir + 0.45 * blue",
            {
                "blue": img.select("CMI_C01"),
                "red": img.select("CMI_C02"),
                "nir": img.select("CMI_C03"),
            },
        )
        return img.addBands(green)

    # Show at clouds at night (a-mode)
    def showNighta(img):
        # Make normalized infrared
        IR_n = img.select("CMI_C13").unitScale(ee.Number(90), ee.Number(313))
        IR_n = IR_n.expression(
            "ir_p = (1 -IR_n)/1.4",
            {
                "IR_n": IR_n.select("CMI_C13"),
            },
        )

        # Add infrared to rgb bands
        R_ir = img.select("CMI_C02").max(IR_n)
        G_ir = img.select("CMI_GREEN").max(IR_n)
        B_ir = img.select("CMI_C01").max(IR_n)

        return img.addBands([R_ir, G_ir, B_ir], overwrite=True)

    # Show at clouds at night (b-mode)
    def showNightb(img):
        night = img.select("CMI_C03").unitScale(0, 0.016).subtract(1).multiply(-1)

        cmi11 = img.select("CMI_C11").unitScale(100, 310)
        cmi13 = img.select("CMI_C13").unitScale(100, 300)
        cmi15 = img.select("CMI_C15").unitScale(100, 310)
        iNight = cmi15.addBands([cmi13, cmi11]).clamp(0, 1).subtract(1).multiply(-1)

        iRGBNight = iNight.visualize(**{"min": 0, "max": 1, "gamma": 1.4}).updateMask(
            night
        )

        iRGB = img.visualize(
            **{
                "bands": ["CMI_C02", "CMI_C03", "CMI_C01"],
                "min": 0.15,
                "max": 1,
                "gamma": 1.4,
            }
        )
        return iRGB.blend(iRGBNight).set(
            "system:time_start", img.get("system:time_start")
        )

    # Scales select bands for visualization.
    def scaleForVis(img):
        return (
            img.select(["CMI_C01", "CMI_GREEN", "CMI_C02", "CMI_C03", "CMI_C05"])
            .resample("bicubic")
            .log10()
            .interpolate([-1.6, 0.176], [0, 1], "clamp")
            .unmask(0)
            .set("system:time_start", img.get("system:time_start"))
        )

    # Wraps previous functions.
    def processForVis(img):
        if show_night[0]:
            if show_night[1] == "a_mode":
                return scaleForVis(showNighta(addGreenBand(applyScaleAndOffset(img))))

            else:
                return showNightb(applyScaleAndOffset(img))

        else:
            return scaleForVis(addGreenBand(applyScaleAndOffset(img)))

    return col.filterDate(start_date, end_date).filterBounds(region).map(processForVis)


def goes_fire_timeseries(
    start_date="2020-09-05T15:00",
    end_date="2020-09-06T02:00",
    data="GOES-17",
    scan="full_disk",
    region=None,
    merge=True,
):
    """Create a time series of GOES Fire data. The code is adapted from Justin Braaten's code: https://code.earthengine.google.com/8a083a7fb13b95ad4ba148ed9b65475e.
    Credits to Justin Braaten. See also https://jstnbraaten.medium.com/goes-in-earth-engine-53fbc8783c16

    Args:
        start_date (str, optional): The start date of the time series. Defaults to "2020-09-05T15:00".
        end_date (str, optional): The end date of the time series. Defaults to "2020-09-06T02:00".
        data (str, optional): The GOES satellite data to use. Defaults to "GOES-17".
        scan (str, optional): The GOES scan to use. Defaults to "full_disk".
        region (ee.Geometry, optional): The region of interest. Defaults to None.
        merge (bool, optional): Whether to merge the fire timeseries with GOES CMI timeseries. Defaults to True.

    Raises:
        ValueError: The data must be either GOES-16 or GOES-17.
        ValueError: The scan must be either full_disk or conus.

    Returns:
        ee.ImageCollection: GOES fire timeseries.
    """

    if data not in ["GOES-16", "GOES-17"]:
        raise ValueError("The data must be either GOES-16 or GOES-17.")

    if scan.lower() not in ["full_disk", "conus"]:
        raise ValueError("The scan must be either full_disk or conus.")

    scan_types = {
        "full_disk": "FDCF",
        "conus": "FDCC",
    }

    if region is None:
        region = ee.Geometry.BBox(-123.17, 36.56, -118.22, 40.03)

    # Get the fire/hotspot characterization dataset.
    col = ee.ImageCollection(f"NOAA/GOES/{data[-2:]}/{scan_types[scan.lower()]}")
    fdcCol = col.filterDate(start_date, end_date)

    # Identify fire-detected pixels of medium to high confidence.
    fireMaskCodes = [10, 30, 11, 31, 12, 32, 13, 33, 14, 34, 15, 35]
    confVals = [1.0, 1.0, 0.9, 0.9, 0.8, 0.8, 0.5, 0.5, 0.3, 0.3, 0.1, 0.1]
    defaultConfVal = 0

    def fdcVis(img):
        confImg = img.remap(fireMaskCodes, confVals, defaultConfVal, "Mask")
        return (
            confImg.gte(0.3)
            .selfMask()
            .set("system:time_start", img.get("system:time_start"))
        )

    fdcVisCol = fdcCol.map(fdcVis)
    if not merge:
        return fdcVisCol
    else:
        geosVisCol = goes_timeseries(start_date, end_date, data, scan, region)
        # Join the fire collection to the CMI collection.
        joinFilter = ee.Filter.equals(
            **{"leftField": "system:time_start", "rightField": "system:time_start"}
        )
        joinedCol = ee.Join.saveFirst("match").apply(geosVisCol, fdcVisCol, joinFilter)

        def overlayVis(img):
            cmi = ee.Image(img).visualize(
                **{
                    "bands": ["CMI_C02", "CMI_GREEN", "CMI_C01"],
                    "min": 0,
                    "max": 0.8,
                    "gamma": 0.8,
                }
            )
            fdc = ee.Image(img.get("match")).visualize(
                **{"palette": ["ff5349"], "min": 0, "max": 1, "opacity": 0.7}
            )
            return cmi.blend(fdc).set("system:time_start", img.get("system:time_start"))

        cmiFdcVisCol = ee.ImageCollection(joinedCol.map(overlayVis))
        return cmiFdcVisCol


def goes_timelapse(
    roi=None,
    out_gif=None,
    start_date="2021-10-24T14:00:00",
    end_date="2021-10-25T01:00:00",
    data="GOES-17",
    scan="full_disk",
    bands=["CMI_C02", "CMI_GREEN", "CMI_C01"],
    dimensions=768,
    framesPerSecond=10,
    date_format="YYYY-MM-dd HH:mm",
    xy=("3%", "3%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="#ffffff",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    loop=0,
    crs=None,
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    mp4=False,
    fading=False,
    **kwargs,
):
    """Create a timelapse of GOES data. The code is adapted from Justin Braaten's code: https://code.earthengine.google.com/57245f2d3d04233765c42fb5ef19c1f4.
    Credits to Justin Braaten. See also https://jstnbraaten.medium.com/goes-in-earth-engine-53fbc8783c16

    Args:
        roi (ee.Geometry, optional): The region of interest. Defaults to None.
        out_gif (str): The file path to save the gif.
        start_date (str, optional): The start date of the time series. Defaults to "2021-10-24T14:00:00".
        end_date (str, optional): The end date of the time series. Defaults to "2021-10-25T01:00:00".
        data (str, optional): The GOES satellite data to use. Defaults to "GOES-17".
        scan (str, optional): The GOES scan to use. Defaults to "full_disk".
        bands (list, optional): The bands to visualize. Defaults to ["CMI_C02", "CMI_GREEN", "CMI_C01"].
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        date_format (str, optional): The date format to use. Defaults to "YYYY-MM-dd HH:mm".
        xy (tuple, optional): Top left corner of the text. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.        loop (int, optional): controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        crs (str, optional): The coordinate reference system to use, e.g., "EPSG:3857". Defaults to None.
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Line width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        mp4 (bool, optional): Whether to save the animation as an mp4 file. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).
    Raises:
        Exception: Raise exception.
    """

    try:
        if "region" in kwargs:
            roi = kwargs["region"]

        if out_gif is None:
            out_gif = os.path.abspath(f"goes_{random_string(3)}.gif")

        visParams = {
            "bands": bands,
            "min": 0,
            "max": 0.8,
        }
        col = goes_timeseries(start_date, end_date, data, scan, roi)
        col = col.select(bands).map(
            lambda img: img.visualize(**visParams).set(
                {
                    "system:time_start": img.get("system:time_start"),
                }
            )
        )
        if overlay_data is not None:
            col = add_overlay(
                col, overlay_data, overlay_color, overlay_width, overlay_opacity
            )

        if roi is None:
            roi = ee.Geometry.Polygon(
                [
                    [
                        [-159.5954, 60.4088],
                        [-159.5954, 24.5178],
                        [-114.2438, 24.5178],
                        [-114.2438, 60.4088],
                    ]
                ],
                None,
                False,
            )

        if crs is None:
            crs = col.first().projection()

        videoParams = {
            "bands": ["vis-red", "vis-green", "vis-blue"],
            "min": 0,
            "max": 255,
            "dimensions": dimensions,
            "framesPerSecond": framesPerSecond,
            "region": roi,
            "crs": crs,
        }

        if text_sequence is None:
            text_sequence = image_dates(col, date_format=date_format).getInfo()

        download_ee_video(col, videoParams, out_gif)

        if os.path.exists(out_gif):
            add_text_to_gif(
                out_gif,
                out_gif,
                xy,
                text_sequence,
                font_type,
                font_size,
                font_color,
                add_progress_bar,
                progress_bar_color,
                progress_bar_height,
                duration=1000 / framesPerSecond,
                loop=loop,
            )

            try:
                reduce_gif_size(out_gif)

                if isinstance(fading, bool):
                    fading = int(fading)
                if fading > 0:
                    gif_fading(out_gif, out_gif, duration=fading, verbose=False)

            except Exception as _:
                pass

            if mp4:
                out_mp4 = out_gif.replace(".gif", ".mp4")
                gif_to_mp4(out_gif, out_mp4)

            return out_gif

    except Exception as e:
        raise Exception(e)


def goes_fire_timelapse(
    roi=None,
    out_gif=None,
    start_date="2020-09-05T15:00",
    end_date="2020-09-06T02:00",
    data="GOES-17",
    scan="full_disk",
    dimensions=768,
    framesPerSecond=10,
    date_format="YYYY-MM-dd HH:mm",
    xy=("3%", "3%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="#ffffff",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    loop=0,
    crs=None,
    overlay_data=None,
    overlay_color="#000000",
    overlay_width=1,
    overlay_opacity=1.0,
    mp4=False,
    fading=False,
    **kwargs,
):
    """Create a timelapse of GOES fire data. The code is adapted from Justin Braaten's code: https://code.earthengine.google.com/8a083a7fb13b95ad4ba148ed9b65475e.
    Credits to Justin Braaten. See also https://jstnbraaten.medium.com/goes-in-earth-engine-53fbc8783c16

    Args:
        out_gif (str): The file path to save the gif.
        start_date (str, optional): The start date of the time series. Defaults to "2021-10-24T14:00:00".
        end_date (str, optional): The end date of the time series. Defaults to "2021-10-25T01:00:00".
        data (str, optional): The GOES satellite data to use. Defaults to "GOES-17".
        scan (str, optional): The GOES scan to use. Defaults to "full_disk".
        region (ee.Geometry, optional): The region of interest. Defaults to None.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        date_format (str, optional): The date format to use. Defaults to "YYYY-MM-dd HH:mm".
        xy (tuple, optional): Top left corner of the text. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        loop (int, optional): controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        crs (str, optional): The coordinate reference system to use, e.g., "EPSG:3857". Defaults to None.
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        mp4 (bool, optional): Whether to convert the GIF to MP4. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).

    Raises:
        Exception: Raise exception.
    """

    try:
        if "region" in kwargs:
            roi = kwargs["region"]

        if out_gif is None:
            out_gif = os.path.abspath(f"goes_fire_{random_string(3)}.gif")

        if roi is None:
            roi = ee.Geometry.BBox(-123.17, 36.56, -118.22, 40.03)

        col = goes_fire_timeseries(start_date, end_date, data, scan, roi)
        if overlay_data is not None:
            col = add_overlay(
                col, overlay_data, overlay_color, overlay_width, overlay_opacity
            )

        # visParams = {
        #     "bands": ["CMI_C02", "CMI_GREEN", "CMI_C01"],
        #     "min": 0,
        #     "max": 0.8,
        #     "dimensions": dimensions,
        #     "framesPerSecond": framesPerSecond,
        #     "region": region,
        #     "crs": col.first().projection(),
        # }

        if crs is None:
            crs = col.first().projection()

        cmiFdcVisParams = {
            "dimensions": dimensions,
            "framesPerSecond": framesPerSecond,
            "region": roi,
            "crs": crs,
        }

        if text_sequence is None:
            text_sequence = image_dates(col, date_format=date_format).getInfo()

        download_ee_video(col, cmiFdcVisParams, out_gif)

        if os.path.exists(out_gif):
            add_text_to_gif(
                out_gif,
                out_gif,
                xy,
                text_sequence,
                font_type,
                font_size,
                font_color,
                add_progress_bar,
                progress_bar_color,
                progress_bar_height,
                duration=1000 / framesPerSecond,
                loop=loop,
            )

            try:
                reduce_gif_size(out_gif)
                if isinstance(fading, bool):
                    fading = int(fading)
                if fading > 0:
                    gif_fading(out_gif, out_gif, duration=fading, verbose=False)

            except Exception as _:
                pass

            if mp4:
                out_mp4 = out_gif.replace(".gif", ".mp4")
                gif_to_mp4(out_gif, out_mp4)

            return out_gif

    except Exception as e:
        raise Exception(e)


def modis_ndvi_doy_ts(
    data="Terra", band="NDVI", start_date=None, end_date=None, region=None
):
    """Create MODIS NDVI timeseries. The source code is adapted from https://developers.google.com/earth-engine/tutorials/community/modis-ndvi-time-series-animation.

    Args:
        data (str, optional): Either "Terra" or "Aqua". Defaults to "Terra".
        band (str, optional): Either the "NDVI" or "EVI" band. Defaults to "NDVI".
        start_date (str, optional): The start date used to filter the image collection, e.g., "2013-01-01". Defaults to None.
        end_date (str, optional): The end date used to filter the image collection. Defaults to None.
        region (ee.Geometry, optional): The geometry used to filter the image collection. Defaults to None.

    Returns:
        ee.ImageCollection: The MODIS NDVI time series.
    """
    if data not in ["Terra", "Aqua"]:
        raise Exception("data must be 'Terra' or 'Aqua'.")

    if band not in ["NDVI", "EVI"]:
        raise Exception("band must be 'NDVI' or 'EVI'.")

    if region is not None:
        if isinstance(region, ee.Geometry) or isinstance(region, ee.FeatureCollection):
            pass
        else:
            raise Exception("region must be an ee.Geometry or ee.FeatureCollection.")

    if data == "Terra":
        col = ee.ImageCollection("MODIS/006/MOD13A2").select(band)
    else:
        col = ee.ImageCollection("MODIS/006/MYD13A2").select(band)

    if (start_date is not None) and (end_date is not None):
        col = col.filterDate(start_date, end_date)

    def set_doy(img):
        doy = ee.Date(img.get("system:time_start")).getRelative("day", "year")
        return img.set("doy", doy)

    col = col.map(set_doy)

    # Get a collection of distinct images by 'doy'.
    distinctDOY = col.filterDate("2013-01-01", "2014-01-01")

    # Define a filter that identifies which images from the complete
    # collection match the DOY from the distinct DOY collection.
    filter = ee.Filter.equals(**{"leftField": "doy", "rightField": "doy"})

    # Define a join.
    join = ee.Join.saveAll("doy_matches")

    # Apply the join and convert the resulting FeatureCollection to an
    # ImageCollection.
    joinCol = ee.ImageCollection(join.apply(distinctDOY, col, filter))

    # Apply median reduction among matching DOY collections.

    def match_doy(img):
        doyCol = ee.ImageCollection.fromImages(img.get("doy_matches"))
        return doyCol.reduce(ee.Reducer.median())

    comp = joinCol.map(match_doy)

    if region is not None:
        return comp.map(lambda img: img.clip(region))
    else:
        return comp


def modis_ndvi_timelapse(
    roi=None,
    out_gif=None,
    data="Terra",
    band="NDVI",
    start_date=None,
    end_date=None,
    dimensions=768,
    framesPerSecond=10,
    crs="EPSG:3857",
    xy=("3%", "3%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="#ffffff",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    loop=0,
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    mp4=False,
    fading=False,
    **kwargs,
):
    """Create MODIS NDVI timelapse. The source code is adapted from https://developers.google.com/earth-engine/tutorials/community/modis-ndvi-time-series-animation.

    Args:
        roi (ee.Geometry, optional): The geometry used to filter the image collection. Defaults to None.
        out_gif (str): The output gif file path. Defaults to None.
        data (str, optional): Either "Terra" or "Aqua". Defaults to "Terra".
        band (str, optional): Either the "NDVI" or "EVI" band. Defaults to "NDVI".
        start_date (str, optional): The start date used to filter the image collection, e.g., "2013-01-01". Defaults to None.
        end_date (str, optional): The end date used to filter the image collection. Defaults to None.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        crs (str, optional): The coordinate reference system to use. Defaults to "EPSG:3857".
        xy (tuple, optional): Top left corner of the text. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        loop (int, optional): controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        mp4 (bool, optional): Whether to convert the output gif to mp4. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).

    """

    if roi is None:
        roi = ee.Geometry.Polygon(
            [
                [
                    [-18.6983, 38.1446],
                    [-18.6983, -36.1630],
                    [52.2293, -36.1630],
                    [52.2293, 38.1446],
                ]
            ],
            None,
            False,
        )

    if out_gif is None:
        out_gif = os.path.abspath(f"modis_ndvi_{random_string(3)}.gif")

    try:
        col = modis_ndvi_doy_ts(data, band, start_date, end_date, roi)

        # Define RGB visualization parameters.
        visParams = {
            "min": 0.0,
            "max": 9000.0,
            "palette": [
                "FFFFFF",
                "CE7E45",
                "DF923D",
                "F1B555",
                "FCD163",
                "99B718",
                "74A901",
                "66A000",
                "529400",
                "3E8601",
                "207401",
                "056201",
                "004C00",
                "023B01",
                "012E01",
                "011D01",
                "011301",
            ],
        }

        # Create RGB visualization images for use as animation frames.
        rgbVis = col.map(lambda img: img.visualize(**visParams).clip(roi))

        if overlay_data is not None:
            rgbVis = add_overlay(
                rgbVis,
                overlay_data,
                overlay_color,
                overlay_width,
                overlay_opacity,
                roi,
            )

        # Define GIF visualization arguments.
        videoArgs = {
            "region": roi,
            "dimensions": dimensions,
            "crs": crs,
            "framesPerSecond": framesPerSecond,
        }

        download_ee_video(rgbVis, videoArgs, out_gif)

        if text_sequence is None:
            text = rgbVis.aggregate_array("system:index").getInfo()
            text_sequence = [d.replace("_", "-")[5:] for d in text]

        if os.path.exists(out_gif):
            add_text_to_gif(
                out_gif,
                out_gif,
                xy,
                text_sequence,
                font_type,
                font_size,
                font_color,
                add_progress_bar,
                progress_bar_color,
                progress_bar_height,
                duration=1000 / framesPerSecond,
                loop=loop,
            )

            try:
                reduce_gif_size(out_gif)
                if isinstance(fading, bool):
                    fading = int(fading)
                if fading > 0:
                    gif_fading(out_gif, out_gif, duration=fading, verbose=False)

            except Exception as _:
                pass

        if mp4:
            out_mp4 = out_gif.replace(".gif", ".mp4")
            gif_to_mp4(out_gif, out_mp4)

        return out_gif

    except Exception as e:
        raise Exception(e)


def modis_ocean_color_timeseries(
    satellite,
    start_date,
    end_date,
    region=None,
    bands=None,
    frequency="year",
    reducer="median",
    drop_empty=True,
    date_format=None,
    parallel_scale=1,
):
    """Creates a ocean color timeseries from MODIS. https://developers.google.com/earth-engine/datasets/catalog/NASA_OCEANDATA_MODIS-Aqua_L3SMI

    Args:
        satellite (str): The satellite to use, can be either "Terra" or "Aqua".
        start_date (str): The start date of the timeseries. It must be formatted like this: 'YYYY-MM-dd'.
        end_date (str): The end date of the timeseries. It must be formatted like this: 'YYYY-MM-dd'.
        region (ee.Geometry, optional): The region to use to filter the collection of images. It must be an ee.Geometry object. Defaults to None.
        bands (list, optional): The list of bands to use to create the timeseries. It must be a list of strings. Defaults to None.
        frequency (str, optional): The frequency of the timeseries. It must be one of the following: 'year', 'month', 'day'. Defaults to 'year'.
        reducer (str, optional):  The reducer to use to reduce the collection of images to a single value. It can be one of the following: 'median', 'mean', 'min', 'max', 'variance', 'sum'. Defaults to 'median'.
        drop_empty (bool, optional): Whether to drop empty images from the timeseries. Defaults to True.
        date_format (str, optional): A pattern, as described at http://joda-time.sourceforge.net/apidocs/org/joda/time/format/DateTimeFormat.html. Defaults to 'YYYY-MM-dd'.
        parallel_scale (int, optional): A scaling factor used to limit memory use; using a larger parallel_scale (e.g. 2 or 4) may enable computations that run out of memory with the default. Defaults to 1.

    Returns:
        ee.ImageCollection: The timeseries.
    """

    if satellite not in ["Terra", "Aqua"]:
        raise Exception("Satellite must be 'Terra' or 'Aqua'.")

    allowed_frequency = ["year", "quarter", "month", "week", "day"]
    if frequency not in allowed_frequency:
        raise Exception(
            "Frequency must be one of the following: {}".format(allowed_frequency)
        )

    if region is not None:
        if isinstance(region, ee.Geometry) or isinstance(region, ee.FeatureCollection):
            pass
        else:
            raise Exception("region must be an ee.Geometry or ee.FeatureCollection.")

    col = ee.ImageCollection(f"NASA/OCEANDATA/MODIS-{satellite}/L3SMI").filterDate(
        start_date, end_date
    )

    ts = create_timeseries(
        col,
        start_date,
        end_date,
        region,
        bands,
        frequency,
        reducer,
        drop_empty,
        date_format,
        parallel_scale,
    )

    return ts


def modis_ocean_color_timelapse(
    satellite,
    start_date,
    end_date,
    roi=None,
    bands=None,
    frequency="year",
    reducer="median",
    date_format=None,
    out_gif=None,
    palette="coolwarm",
    vis_params=None,
    dimensions=768,
    frames_per_second=5,
    crs="EPSG:3857",
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    add_colorbar=True,
    colorbar_width=6.0,
    colorbar_height=0.4,
    colorbar_label="Sea Surface Temperature (°C)",
    colorbar_label_size=12,
    colorbar_label_weight="normal",
    colorbar_tick_size=10,
    colorbar_bg_color="white",
    colorbar_orientation="horizontal",
    colorbar_dpi="figure",
    colorbar_xy=None,
    colorbar_size=(300, 300),
    loop=0,
    mp4=False,
    fading=False,
):
    """Creates a ocean color timelapse from MODIS. https://developers.google.com/earth-engine/datasets/catalog/NASA_OCEANDATA_MODIS-Aqua_L3SMI

    Args:
        satellite (str): The satellite to use, can be either "Terra" or "Aqua".
        start_date (str): The start date of the timeseries. It must be formatted like this: 'YYYY-MM-dd'.
        end_date (str): The end date of the timeseries. It must be formatted like this: 'YYYY-MM-dd'.
        roi (ee.Geometry, optional): The region to use to filter the collection of images. It must be an ee.Geometry object. Defaults to None.
        bands (list, optional): A list of band names to use in the timelapse. Defaults to None.
        frequency (str, optional): The frequency of the timeseries. It must be one of the following: 'year', 'month', 'day', 'hour', 'minute', 'second'. Defaults to 'year'.
        reducer (str, optional):  The reducer to use to reduce the collection of images to a single value. It can be one of the following: 'median', 'mean', 'min', 'max', 'variance', 'sum'. Defaults to 'median'.
        drop_empty (bool, optional): Whether to drop empty images from the timeseries. Defaults to True.
        date_format (str, optional): A pattern, as described at http://joda-time.sourceforge.net/apidocs/org/joda/time/format/DateTimeFormat.html. Defaults to 'YYYY-MM-dd'.
        out_gif (str): The output gif file path. Defaults to None.
        palette (list, optional): A list of colors to render a single-band image in the timelapse. Defaults to None.
        vis_params (dict, optional): A dictionary of visualization parameters to use in the timelapse. Defaults to None. See more at https://developers.google.com/earth-engine/guides/image_visualization.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        crs (str, optional): The coordinate reference system to use. Defaults to "EPSG:3857".
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Lower left corner of the title. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        add_text (bool, optional): Whether to add animated text to the timelapse. Defaults to True.
        title_xy (tuple, optional): Lower left corner of the text sequency. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        add_colorbar (bool, optional): Whether to add a colorbar to the timelapse. Defaults to False.
        colorbar_width (float, optional): Width of the colorbar. Defaults to 6.0.
        colorbar_height (float, optional): Height of the colorbar. Defaults to 0.4.
        colorbar_label (str, optional): Label for the colorbar. Defaults to None.
        colorbar_label_size (int, optional): Font size for the colorbar label. Defaults to 12.
        colorbar_label_weight (str, optional): Font weight for the colorbar label. Defaults to 'normal'.
        colorbar_tick_size (int, optional): Font size for the colorbar ticks. Defaults to 10.
        colorbar_bg_color (str, optional): Background color for the colorbar, can be color like "white", "black". Defaults to None.
        colorbar_orientation (str, optional): Orientation of the colorbar. Defaults to 'horizontal'.
        colorbar_dpi (str, optional): DPI for the colorbar, can be numbers like 100, 300. Defaults to 'figure'.
        colorbar_xy (tuple, optional): Lower left corner of the colorbar. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        colorbar_size (tuple, optional): Size of the colorbar. It can be formatted like this: (300, 300). Defaults to (300, 300).
        loop (int, optional): Controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        mp4 (bool, optional): Whether to create an mp4 file. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).

    Returns:
        str: File path to the timelapse gif.
    """
    collection = modis_ocean_color_timeseries(
        satellite, start_date, end_date, roi, bands, frequency, reducer, date_format
    )

    if bands is None:
        bands = ["sst"]

    if len(bands) == 1 and palette is None:
        palette = "coolwarm"

    if roi is None:
        roi = ee.Geometry.BBox(-99.755133, 18.316722, -79.761194, 31.206929)

    out_gif = create_timelapse(
        collection,
        start_date,
        end_date,
        roi,
        bands,
        frequency,
        reducer,
        date_format,
        out_gif,
        palette,
        vis_params,
        dimensions,
        frames_per_second,
        crs,
        overlay_data,
        overlay_color,
        overlay_width,
        overlay_opacity,
        title,
        title_xy,
        add_text,
        text_xy,
        text_sequence,
        font_type,
        font_size,
        font_color,
        add_progress_bar,
        progress_bar_color,
        progress_bar_height,
        add_colorbar,
        colorbar_width,
        colorbar_height,
        colorbar_label,
        colorbar_label_size,
        colorbar_label_weight,
        colorbar_tick_size,
        colorbar_bg_color,
        colorbar_orientation,
        colorbar_dpi,
        colorbar_xy,
        colorbar_size,
        loop,
        mp4,
        fading,
    )

    return out_gif


def dynamic_world_timeseries(
    region,
    start_date="2016-01-01",
    end_date="2021-12-31",
    cloud_pct=30,
    frequency="year",
    reducer="mode",
    drop_empty=True,
    date_format=None,
    return_type="hillshade",
    parallel_scale=1,
):
    """Create Dynamic World timeseries.

    Args:
        region (ee.Geometry | ee.FeatureCollection): The region of interest.
        start_date (str | ee.Date): The start date of the query. Default to "2016-01-01".
        end_date (str | ee.Date): The end date of the query. Default to "2021-12-31".
        cloud_pct (int, optional): The cloud percentage threshold (<=). Defaults to 30.
        frequency (str, optional): The frequency of the timeseries. It must be one of the following: 'year', 'month', 'day', 'hour', 'minute', 'second'. Defaults to 'year'.
        reducer (str, optional): The reducer to be used. Defaults to "mode".
        drop_empty (bool, optional): Whether to drop empty images from the timeseries. Defaults to True.
        date_format (str, optional): A pattern, as described at http://joda-time.sourceforge.net/apidocs/org/joda/time/format/DateTimeFormat.html. Defaults to 'YYYY-MM-dd'.
        return_type (str, optional): The type of image to be returned. Can be one of 'hillshade', 'visualize', 'class', or 'probability'. Default to "hillshade".
        parallel_scale (int, optional): A scaling factor used to limit memory use; using a larger parallel_scale (e.g. 2 or 4) may enable computations that run out of memory with the default. Defaults to 1.

    Returns:
        ee.ImageCollection: An ImageCollection of the Dynamic World land cover timeseries.
    """
    if return_type not in ["hillshade", "visualize", "class", "probability"]:
        raise ValueError(
            f"{return_type} must be one of 'hillshade', 'visualize', 'class', or 'probability'."
        )

    if (
        isinstance(region, ee.FeatureCollection)
        or isinstance(region, ee.Feature)
        or isinstance(region, ee.Geometry)
    ):
        pass
    else:
        raise ValueError(
            f"{region} must be one of ee.FeatureCollection, ee.Feature, or ee.Geometry."
        )

    if cloud_pct < 0 or cloud_pct > 100:
        raise ValueError(f"{cloud_pct} must be between 0 and 100.")

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterDate(start_date, end_date)
        .filterBounds(region)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", cloud_pct))
    )

    ids = s2.aggregate_array("system:index")

    dw = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filter(
        ee.Filter.inList("system:index", ids)
    )

    collection = dw.select("label")

    dwVisParams = {
        "min": 0,
        "max": 8,
        "palette": [
            "#419BDF",
            "#397D49",
            "#88B053",
            "#7A87C6",
            "#E49635",
            "#DFC35A",
            "#C4281B",
            "#A59B8F",
            "#B39FE1",
        ],
    }

    images = create_timeseries(
        collection,
        start_date,
        end_date,
        region,
        None,
        frequency,
        reducer,
        drop_empty,
        date_format,
        parallel_scale,
    )

    if return_type == "class":
        return images
    elif return_type == "visualize":
        result = images.map(lambda img: img.visualize(**dwVisParams))
        return result
    else:
        # Create a Top-1 Probability Hillshade Visualization
        probabilityBands = [
            "water",
            "trees",
            "grass",
            "flooded_vegetation",
            "crops",
            "shrub_and_scrub",
            "built",
            "bare",
            "snow_and_ice",
        ]

        # Select probability bands
        probabilityCol = dw.select(probabilityBands)

        prob_col = create_timeseries(
            probabilityCol,
            start_date,
            end_date,
            region,
            None,
            frequency,
            "mean",
            drop_empty,
            date_format,
            parallel_scale,
        )

        prob_images = ee.ImageCollection(
            prob_col.map(
                lambda img: img.reduce(ee.Reducer.max()).set(
                    "system:time_start", img.get("system:time_start")
                )
            )
        )

        if return_type == "probability":
            return prob_images

        elif return_type == "hillshade":
            count = prob_images.size()
            nums = ee.List.sequence(0, count.subtract(1))

            def create_hillshade(d):
                proj = ee.Projection("EPSG:3857").atScale(10)
                img = ee.Image(images.toList(images.size()).get(d))
                prob_img = ee.Image(prob_images.toList(prob_images.size()).get(d))
                prob_img = prob_img.setDefaultProjection(proj)
                top1Confidence = prob_img.multiply(100).int()
                hillshade = ee.Terrain.hillshade(top1Confidence).divide(255)
                rgbImage = img.visualize(**dwVisParams).divide(255)
                probabilityHillshade = rgbImage.multiply(hillshade)
                return probabilityHillshade.set(
                    "system:time_start", img.get("system:time_start")
                )

            result = ee.ImageCollection(nums.map(create_hillshade))
            return result


def sentinel1_timelapse(
    roi,
    out_gif=None,
    start_year=2015,
    end_year=None,
    start_date="01-01",
    end_date="12-31",
    bands=["VV"],
    frequency="year",
    reducer="median",
    date_format=None,
    palette="Greys",
    vis_params=None,
    dimensions=768,
    frames_per_second=10,
    crs="EPSG:3857",
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    orbit=["ascending", "descending"],
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    add_colorbar=False,
    colorbar_width=6.0,
    colorbar_height=0.4,
    colorbar_label=None,
    colorbar_label_size=12,
    colorbar_label_weight="normal",
    colorbar_tick_size=10,
    colorbar_bg_color=None,
    colorbar_orientation="horizontal",
    colorbar_dpi="figure",
    colorbar_xy=None,
    colorbar_size=(300, 300),
    loop=0,
    mp4=False,
    fading=False,
    **kwargs,
):
    """Create a timelapse from any ee.ImageCollection.

    Args:
        roi (ee.Geometry, optional): The region to use to filter the collection of images. It must be an ee.Geometry object. Defaults to None.
        out_gif (str): The output gif file path. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 2015.
        end_year (int, optional): Ending year for the timelapse. Defaults to the current year.
        start_date (str, optional): Starting date (month-day) each year for filtering ImageCollection. Defaults to '01-01'.
        end_date (str, optional): Ending date (month-day) each year for filtering ImageCollection. Defaults to '12-31'.
        bands (list, optional): A list of band names to use in the timelapse. Can be one of ['VV'],['HV'],['VH'],['HH'],['VV','VH'] or ['HH','HV']
        frequency (str, optional): The frequency of the timeseries. It must be one of the following: 'year', 'month', 'day', 'hour', 'minute', 'second'. Defaults to 'year'.
        reducer (str, optional):  The reducer to use to reduce the collection of images to a single value. It can be one of the following: 'median', 'mean', 'min', 'max', 'variance', 'sum'. Defaults to 'median'.
        drop_empty (bool, optional): Whether to drop empty images from the timeseries. Defaults to True.
        date_format (str, optional): A pattern, as described at http://joda-time.sourceforge.net/apidocs/org/joda/time/format/DateTimeFormat.html. Defaults to 'YYYY-MM-dd'.
        palette (list, optional): A list of colors to render a single-band image in the timelapse. Defaults to None.
        vis_params (dict, optional): A dictionary of visualization parameters to use in the timelapse. Defaults to None. See more at https://developers.google.com/earth-engine/guides/image_visualization.
        dimensions (int, optional): a number or pair of numbers (in format 'WIDTHxHEIGHT') Maximum dimensions of the thumbnail to render, in pixels. If only one number is passed, it is used as the maximum, and the other dimension is computed by proportional scaling. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        crs (str, optional): The coordinate reference system to use. Defaults to "EPSG:3857".
        overlay_data (int, str, list, optional): Administrative boundary to be drawn on the timelapse. Defaults to None.
        overlay_color (str, optional): Color for the overlay data. Can be any color name or hex color code. Defaults to 'black'.
        overlay_width (int, optional): Width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        orbit (list, optional): List of orbit directions to include. Can be ['ascending'], ['descending'], or ['ascending', 'descending']. Defaults to both.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Lower left corner of the title. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        add_text (bool, optional): Whether to add animated text to the timelapse. Defaults to True.
        title_xy (tuple, optional): Lower left corner of the text sequency. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        text_sequence (int, str, list, optional): Text to be drawn. It can be an integer number, a string, or a list of strings. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. It can be a string (e.g., 'red'), rgb tuple (e.g., (255, 127, 0)), or hex code (e.g., '#ff00ff').  Defaults to '#000000'.
        add_progress_bar (bool, optional): Whether to add a progress bar at the bottom of the GIF. Defaults to True.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        add_colorbar (bool, optional): Whether to add a colorbar to the timelapse. Defaults to False.
        colorbar_width (float, optional): Width of the colorbar. Defaults to 6.0.
        colorbar_height (float, optional): Height of the colorbar. Defaults to 0.4.
        colorbar_label (str, optional): Label for the colorbar. Defaults to None.
        colorbar_label_size (int, optional): Font size for the colorbar label. Defaults to 12.
        colorbar_label_weight (str, optional): Font weight for the colorbar label. Defaults to 'normal'.
        colorbar_tick_size (int, optional): Font size for the colorbar ticks. Defaults to 10.
        colorbar_bg_color (str, optional): Background color for the colorbar, can be color like "white", "black". Defaults to None.
        colorbar_orientation (str, optional): Orientation of the colorbar. Defaults to 'horizontal'.
        colorbar_dpi (str, optional): DPI for the colorbar, can be numbers like 100, 300. Defaults to 'figure'.
        colorbar_xy (tuple, optional): Lower left corner of the colorbar. It can be formatted like this: (10, 10) or ('15%', '25%'). Defaults to None.
        colorbar_size (tuple, optional): Size of the colorbar. It can be formatted like this: (300, 300). Defaults to (300, 300).
        loop (int, optional): Controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.
        mp4 (bool, optional): Whether to create an mp4 file. Defaults to False.
        fading (int | bool, optional): If True, add fading effect to the timelapse. Defaults to False, no fading. To add fading effect, set it to True (1 second fading duration) or to an integer value (fading duration).
        **kwargs: Arguments for sentinel1_filtering(). Same filters will be applied to all bands.

    Returns:
        str: File path to the timelapse gif.
    """
    from datetime import date

    assert bands in (
        ["VV"],
        ["VH"],
        ["HH"],
        ["HV"],
        ["VV", "VH"],
        ["HH", "HV"],
        ["VH", "VV"],
        ["HV", "HH"],
    ), "Not all Sentinel1 bands are available together."
    if bands in (["VH", "VV"], ["HV", "HH"]):
        bands[0], bands[1] = bands[1], bands[0]
    band = bands[0]

    if end_year is None:
        end_year = date.today().year

    start = f"{start_year}-{start_date}"
    end = f"{end_year}-{end_date}"

    if vis_params is None:
        vis_params = {"min": -30, "max": 0}

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD").filterDate(start, end).filterBounds(roi)
    )

    # Apply orbit filtering
    if orbit:
        # Convert orbit strings to uppercase for consistency
        orbit_upper = [o.upper() for o in orbit]
        orbit_filter = ee.Filter.inList("orbitProperties_pass", orbit_upper)
        collection = collection.filter(orbit_filter)

    collection = sentinel1_filtering(collection, band, **kwargs)

    return create_timelapse(
        collection,
        start,
        end,
        roi,
        bands,
        frequency,
        reducer,
        date_format,
        out_gif,
        palette,
        vis_params,
        dimensions,
        frames_per_second,
        crs,
        overlay_data,
        overlay_color,
        overlay_width,
        overlay_opacity,
        title,
        title_xy,
        add_text,
        text_xy,
        text_sequence,
        font_type,
        font_size,
        font_color,
        add_progress_bar,
        progress_bar_color,
        progress_bar_height,
        add_colorbar,
        colorbar_width,
        colorbar_height,
        colorbar_label,
        colorbar_label_size,
        colorbar_label_weight,
        colorbar_tick_size,
        colorbar_bg_color,
        colorbar_orientation,
        colorbar_dpi,
        colorbar_xy,
        colorbar_size,
        loop,
        mp4,
        fading,
    )


def add_progress_bar_to_gif(
    in_gif,
    out_gif,
    progress_bar_color="blue",
    progress_bar_height=5,
    duration=100,
    loop=0,
):
    """Adds a progress bar to a GIF image.

    Args:
        in_gif (str): The file path to the input GIF image.
        out_gif (str): The file path to the output GIF image.
        progress_bar_color (str, optional): Color for the progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of the progress bar. Defaults to 5.
        duration (int, optional): controls how long each frame will be displayed for, in milliseconds. It is the inverse of the frame rate. Setting it to 100 milliseconds gives 10 frames per second. You can decrease the duration to give a smoother animation.. Defaults to 100.
        loop (int, optional): controls how many times the animation repeats. The default, 1, means that the animation will play once and then stop (displaying the last frame). A value of 0 means that the animation will repeat forever. Defaults to 0.

    """
    import io
    import warnings

    from PIL import Image, ImageDraw, ImageSequence

    warnings.simplefilter("ignore")

    in_gif = os.path.abspath(in_gif)
    out_gif = os.path.abspath(out_gif)

    if not os.path.exists(in_gif):
        print("The input gif file does not exist.")
        return

    if not os.path.exists(os.path.dirname(out_gif)):
        os.makedirs(os.path.dirname(out_gif))

    progress_bar_color = check_color(progress_bar_color)

    try:
        image = Image.open(in_gif)
    except Exception as e:
        raise Exception("An error occurred while opening the gif.")

    count = image.n_frames
    W, H = image.size
    progress_bar_widths = [i * 1.0 / count * W for i in range(1, count + 1)]
    progress_bar_shapes = [
        [(0, H - progress_bar_height), (x, H)] for x in progress_bar_widths
    ]

    try:
        frames = []
        # Loop over each frame in the animated image
        for index, frame in enumerate(ImageSequence.Iterator(image)):
            # Draw the text on the frame
            frame = frame.convert("RGB")
            draw = ImageDraw.Draw(frame)
            # w, h = draw.textsize(text[index])
            draw.rectangle(progress_bar_shapes[index], fill=progress_bar_color)
            del draw

            b = io.BytesIO()
            frame.save(b, format="GIF")
            frame = Image.open(b)

            frames.append(frame)
        # https://www.pythoninformer.com/python-libraries/pillow/creating-animated-gif/
        # Save the frames as a new image

        frames[0].save(
            out_gif,
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=loop,
            optimize=True,
        )
    except Exception as e:
        raise Exception(e)


def vector_to_gif(
    filename,
    out_gif,
    colname,
    vmin=None,
    vmax=None,
    step=1,
    facecolor="black",
    figsize=(10, 8),
    padding=3,
    title=None,
    add_text=True,
    xy=("1%", "1%"),
    fontsize=20,
    add_progress_bar=True,
    progress_bar_color="blue",
    progress_bar_height=5,
    dpi=300,
    fps=10,
    loop=0,
    mp4=False,
    keep_png=False,
    verbose=True,
    open_args={},
    plot_args={},
):
    """Convert a vector to a gif. This function was inspired by by Johannes Uhl's shapefile2gif repo at
            https://github.com/johannesuhl/shapefile2gif. Credits to Johannes Uhl.

    Args:
        filename (str): The input vector file. Can be a directory path or http URL, e.g., "https://i.imgur.com/ZWSZC5z.gif"
        out_gif (str): The output gif file.
        colname (str): The column name of the vector that contains numerical values.
        vmin (float, optional): The minimum value to filter the data. Defaults to None.
        vmax (float, optional): The maximum value to filter the data. Defaults to None.
        step (float, optional): The step to filter the data. Defaults to 1.
        facecolor (str, optional): The color to visualize the data. Defaults to "black".
        figsize (tuple, optional): The figure size. Defaults to (10, 8).
        padding (int, optional): The padding of the figure tight_layout. Defaults to 3.
        title (str, optional): The title of the figure. Defaults to None.
        add_text (bool, optional): Whether to add text to the figure. Defaults to True.
        xy (tuple, optional): The position of the text from the lower-left corner. Defaults to ("1%", "1%").
        fontsize (int, optional): The font size of the text. Defaults to 20.
        add_progress_bar (bool, optional): Whether to add a progress bar to the figure. Defaults to True.
        progress_bar_color (str, optional): The color of the progress bar. Defaults to "blue".
        progress_bar_height (int, optional): The height of the progress bar. Defaults to 5.
        dpi (int, optional): The dpi of the figure. Defaults to 300.
        fps (int, optional): The frames per second (fps) of the gif. Defaults to 10.
        loop (int, optional): The number of loops of the gif. Defaults to 0, infinite loop.
        mp4 (bool, optional): Whether to convert the gif to mp4. Defaults to False.
        keep_png (bool, optional): Whether to keep the png files. Defaults to False.
        verbose (bool, optional): Whether to print the progress. Defaults to True.
        open_args (dict, optional): The arguments for the geopandas.read_file() function. Defaults to {}.
        plot_args (dict, optional): The arguments for the geopandas.GeoDataFrame.plot() function. Defaults to {}.

    """
    import geopandas as gpd
    import matplotlib.pyplot as plt

    out_dir = os.path.dirname(out_gif)
    tmp_dir = os.path.join(out_dir, "tmp_png")
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    if isinstance(filename, str):
        gdf = gpd.read_file(filename, **open_args)
    elif isinstance(filename, gpd.GeoDataFrame):
        gdf = filename
    else:
        raise ValueError(
            "filename must be a string or a geopandas.GeoDataFrame object."
        )

    bbox = gdf.total_bounds

    if colname not in gdf.columns:
        raise Exception(
            f"{colname} is not in the columns of the GeoDataFrame. It must be one of {gdf.columns}"
        )

    values = gdf[colname].unique().tolist()
    values.sort()

    if vmin is None:
        vmin = values[0]
    if vmax is None:
        vmax = values[-1]

    options = range(vmin, vmax + step, step)

    W = bbox[2] - bbox[0]
    H = bbox[3] - bbox[1]

    if xy is None:
        # default text location is 5% width and 5% height of the image.
        xy = (int(0.05 * W), int(0.05 * H))
    elif (xy is not None) and (not isinstance(xy, tuple)) and (len(xy) == 2):
        raise Exception("xy must be a tuple, e.g., (10, 10), ('10%', '10%')")

    elif all(isinstance(item, int) for item in xy) and (len(xy) == 2):
        x, y = xy
        if (x > 0) and (x < W) and (y > 0) and (y < H):
            pass
        else:
            print(
                f"xy is out of bounds. x must be within [0, {W}], and y must be within [0, {H}]"
            )
            return
    elif all(isinstance(item, str) for item in xy) and (len(xy) == 2):
        x, y = xy
        if ("%" in x) and ("%" in y):
            try:
                x = float(x.replace("%", "")) / 100.0 * W
                y = float(y.replace("%", "")) / 100.0 * H
            except Exception:
                raise Exception(
                    "The specified xy is invalid. It must be formatted like this ('10%', '10%')"
                )
    else:
        raise Exception(
            "The specified xy is invalid. It must be formatted like this: (10, 10) or ('10%', '10%')"
        )

    x = bbox[0] + x
    y = bbox[1] + y

    for index, v in enumerate(options):
        if verbose:
            print(f"Processing {index+1}/{len(options)}: {v}...")
        yrdf = gdf[gdf[colname] <= v]
        fig, ax = plt.subplots()
        ax = yrdf.plot(facecolor=facecolor, figsize=figsize, **plot_args)
        ax.set_title(title, fontsize=fontsize)
        ax.set_axis_off()
        ax.set_xlim([bbox[0], bbox[2]])
        ax.set_ylim([bbox[1], bbox[3]])
        if add_text:
            ax.text(x, y, v, fontsize=fontsize)
        fig = ax.get_figure()
        plt.tight_layout(pad=padding)
        fig.savefig(tmp_dir + os.sep + "%s.png" % v, dpi=dpi)
        plt.clf()
        plt.close("all")

    png_to_gif(tmp_dir, out_gif, fps=fps, loop=loop)

    if add_progress_bar:
        add_progress_bar_to_gif(
            out_gif,
            out_gif,
            progress_bar_color,
            progress_bar_height,
            duration=1000 / fps,
            loop=loop,
        )

    if mp4:
        gif_to_mp4(out_gif, out_gif.replace(".gif", ".mp4"))

    if not keep_png:
        shutil.rmtree(tmp_dir)

    if verbose:
        print(f"Done. The GIF is saved to {out_gif}.")


def sentinel1_timelapse_with_samples(
    roi,
    out_gif=None,
    start_year=2015,
    end_year=None,
    start_date="01-01",
    end_date="12-31",
    bands=["VV"],
    frequency="year",
    reducer="median",
    date_format=None,
    palette="Greys",
    vis_params=None,
    dimensions=768,
    frames_per_second=10,
    crs="EPSG:3857",
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    orbit=["ascending", "descending"],
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    add_colorbar=False,
    colorbar_width=6.0,
    colorbar_height=0.4,
    colorbar_label=None,
    colorbar_label_size=12,
    colorbar_label_weight="normal",
    colorbar_tick_size=10,
    colorbar_bg_color=None,
    colorbar_orientation="horizontal",
    colorbar_dpi="figure",
    colorbar_xy=None,
    colorbar_size=(300, 300),
    loop=0,
    mp4=False,
    fading=False,
    sample_points=None,
    sample_point_crs="EPSG:4326",
    marker_colors=None,
    marker_size=50,
    marker_style="cross",
    show_sample_markers=True,
    chart_title="Sentinel-1 Time Series",
    chart_ylabel="Backscatter (dB)",
    chart_position="right",
    chart_size_ratio=0.7,
    spacer_width=20,
    chart_xlabel_format="auto",
    chart_xlabel_interval="auto",
    **kwargs,
):
    """Create a Sentinel-1 timelapse with optional sample points and time series chart.

    Args:
        roi (ee.Geometry): The region to use to filter the collection of images.
        out_gif (str): The output gif file path. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 2015.
        end_year (int, optional): Ending year for the timelapse. Defaults to the current year.
        start_date (str, optional): Starting date (month-day) each year. Defaults to '01-01'.
        end_date (str, optional): Ending date (month-day) each year. Defaults to '12-31'.
        bands (list, optional): A list of band names. Can be ['VV'],['HV'],['VH'],['HH'],['VV','VH'] or ['HH','HV']
        frequency (str, optional): The frequency of the timeseries. Defaults to 'year'.
        reducer (str, optional): The reducer to use. Defaults to 'median'.
        date_format (str, optional): Date format pattern. Defaults to None.
        palette (str, optional): Color palette for single-band visualization. Defaults to 'Greys'.
        vis_params (dict, optional): Visualization parameters. Defaults to None.
        dimensions (int, optional): Maximum dimensions of the thumbnail. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        crs (str, optional): Coordinate reference system. Defaults to "EPSG:3857".
        overlay_data (optional): Administrative boundary overlay. Defaults to None.
        overlay_color (str, optional): Color for overlay data. Defaults to 'black'.
        overlay_width (int, optional): Width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        orbit (list, optional): Orbit directions to include. Defaults to ["ascending", "descending"].
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Position of the title. Defaults to ("2%", "90%").
        add_text (bool, optional): Whether to add animated text. Defaults to True.
        text_xy (tuple, optional): Position of the text. Defaults to ("2%", "2%").
        text_sequence (optional): Text to be drawn. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. Defaults to 'white'.
        add_progress_bar (bool, optional): Whether to add progress bar. Defaults to True.
        progress_bar_color (str, optional): Color for progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of progress bar. Defaults to 5.
        add_colorbar (bool, optional): Whether to add colorbar. Defaults to False.
        colorbar_width (float, optional): Width of colorbar. Defaults to 6.0.
        colorbar_height (float, optional): Height of colorbar. Defaults to 0.4.
        colorbar_label (str, optional): Label for colorbar. Defaults to None.
        colorbar_label_size (int, optional): Font size for colorbar label. Defaults to 12.
        colorbar_label_weight (str, optional): Font weight for colorbar label. Defaults to 'normal'.
        colorbar_tick_size (int, optional): Font size for colorbar ticks. Defaults to 10.
        colorbar_bg_color (str, optional): Background color for colorbar. Defaults to None.
        colorbar_orientation (str, optional): Orientation of colorbar. Defaults to 'horizontal'.
        colorbar_dpi (str, optional): DPI for colorbar. Defaults to 'figure'.
        colorbar_xy (tuple, optional): Position of colorbar. Defaults to None.
        colorbar_size (tuple, optional): Size of colorbar. Defaults to (300, 300).
        loop (int, optional): Number of animation loops. Defaults to 0.
        mp4 (bool, optional): Whether to create mp4 file. Defaults to False.
        fading (bool, optional): Whether to add fading effect. Defaults to False.
        sample_points (list, optional): List of [lon, lat] coordinates for sampling (max 5 points). Defaults to None.
        sample_point_crs (str, optional): CRS for sample points. Defaults to "EPSG:4326".
        marker_colors (list, optional): Colors for markers. Defaults to None (uses default colors).
        marker_size (int, optional): Size of markers. Defaults to 50.
        marker_style (str, optional): Style of markers ('cross', 'circle', 'square'). Defaults to 'cross'.
        show_sample_markers (bool, optional): Whether to show markers on map. Defaults to True.
        chart_title (str, optional): Title for the time series chart. Defaults to "Sentinel-1 Time Series".
        chart_ylabel (str, optional): Y-axis label for chart. Defaults to "Backscatter (dB)".
        chart_position (str, optional): Position of chart ('right', 'left', 'bottom'). Defaults to 'right'.
        chart_size_ratio (float, optional): Size ratio of chart to gif. Defaults to 0.7.
        spacer_width (int, optional): Width of spacer between gif and chart. Defaults to 20.
        chart_xlabel_format (str, optional): Format for x-axis labels ('auto', '%Y-%m', '%m-%d', '%Y-%m-%d'). Defaults to 'auto'.
        chart_xlabel_interval (str, optional): Interval for x-axis labels ('auto', 'day', 'week', 'month', 'year'). Defaults to 'auto'.
        **kwargs: Additional arguments for sentinel1_filtering().

    Returns:
        str: File path to the output GIF with optional chart.
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    from datetime import datetime, date
    import tempfile
    import math

    # Validate sample points
    if sample_points is not None:
        if not isinstance(sample_points, list):
            raise ValueError("sample_points must be a list of [lon, lat] coordinates")
        if len(sample_points) > 5:
            raise ValueError("Maximum 5 sample points are supported")
        if len(sample_points) == 0:
            sample_points = None

    # Set default marker colors if not provided
    if sample_points is not None and marker_colors is None:
        marker_colors = ["red", "blue", "green", "orange", "purple"][
            : len(sample_points)
        ]
    elif sample_points is not None and len(marker_colors) < len(sample_points):
        default_colors = ["red", "blue", "green", "orange", "purple"]
        marker_colors.extend(default_colors[len(marker_colors) : len(sample_points)])

    # Adjust dimensions to avoid Earth Engine limits
    # Calculate optimal dimensions based on ROI
    if isinstance(roi, ee.Geometry):
        roi_bounds = roi.bounds().getInfo()["coordinates"][0]
        min_lon = min([coord[0] for coord in roi_bounds])
        max_lon = max([coord[0] for coord in roi_bounds])
        min_lat = min([coord[1] for coord in roi_bounds])
        max_lat = max([coord[1] for coord in roi_bounds])

        # Calculate aspect ratio
        lon_range = max_lon - min_lon
        lat_range = max_lat - min_lat
        aspect_ratio = lon_range / lat_range if lat_range > 0 else 1

        # Adjust dimensions to stay within Earth Engine limits
        # Max pixels = 26,214,400 (approximately 5120x5120)
        max_pixels = 26214400

        if isinstance(dimensions, int):
            # Single dimension - calculate based on aspect ratio
            if aspect_ratio > 1:
                # Wider than tall
                width = min(dimensions, int(math.sqrt(max_pixels * aspect_ratio)))
                height = int(width / aspect_ratio)
            else:
                # Taller than wide
                height = min(dimensions, int(math.sqrt(max_pixels / aspect_ratio)))
                width = int(height * aspect_ratio)

            # Ensure minimum size
            width = max(256, width)
            height = max(256, height)

            # Final check
            if width * height > max_pixels:
                scale_factor = math.sqrt(max_pixels / (width * height))
                width = int(width * scale_factor)
                height = int(height * scale_factor)

            adjusted_dimensions = f"{width}x{height}"
        else:
            # Already in WxH format
            adjusted_dimensions = dimensions

        print(f"Adjusted dimensions: {adjusted_dimensions}")
    else:
        adjusted_dimensions = dimensions

    # Create the base timelapse
    try:
        base_gif = sentinel1_timelapse(
            roi=roi,
            out_gif=out_gif,
            start_year=start_year,
            end_year=end_year,
            start_date=start_date,
            end_date=end_date,
            bands=bands,
            frequency=frequency,
            reducer=reducer,
            date_format=date_format,
            palette=palette,
            vis_params=vis_params,
            dimensions=adjusted_dimensions,
            frames_per_second=frames_per_second,
            crs=crs,
            overlay_data=overlay_data,
            overlay_color=overlay_color,
            overlay_width=overlay_width,
            overlay_opacity=overlay_opacity,
            orbit=orbit,
            title=title,
            title_xy=title_xy,
            add_text=add_text,
            text_xy=text_xy,
            text_sequence=text_sequence,
            font_type=font_type,
            font_size=font_size,
            font_color=font_color,
            add_progress_bar=add_progress_bar,
            progress_bar_color=progress_bar_color,
            progress_bar_height=progress_bar_height,
            add_colorbar=add_colorbar,
            colorbar_width=colorbar_width,
            colorbar_height=colorbar_height,
            colorbar_label=colorbar_label,
            colorbar_label_size=colorbar_label_size,
            colorbar_label_weight=colorbar_label_weight,
            colorbar_tick_size=colorbar_tick_size,
            colorbar_bg_color=colorbar_bg_color,
            colorbar_orientation=colorbar_orientation,
            colorbar_dpi=colorbar_dpi,
            colorbar_xy=colorbar_xy,
            colorbar_size=colorbar_size,
            loop=loop,
            mp4=False,
            fading=fading,
            **kwargs,
        )
    except Exception as e:
        print(f"Error creating base timelapse: {str(e)}")
        raise e

    # Check if base GIF was created successfully
    if not os.path.exists(base_gif):
        raise FileNotFoundError(f"Base timelapse GIF was not created: {base_gif}")

    # If no sample points, return the base gif (map only)
    if sample_points is None or len(sample_points) == 0:
        print("No sample points provided. Returning map-only timelapse.")
        if mp4:
            gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
        return base_gif

    # Get the Sentinel-1 time series for sampling
    if end_year is None:
        end_year = date.today().year

    start = f"{start_year}-{start_date}"
    end = f"{end_year}-{end_date}"

    # Create collection with error handling
    try:
        collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterDate(start, end)
            .filterBounds(roi)
        )

        # Apply orbit filtering
        if orbit:
            orbit_upper = [o.upper() for o in orbit]
            orbit_filter = ee.Filter.inList("orbitProperties_pass", orbit_upper)
            collection = collection.filter(orbit_filter)

        band = bands[0]
        collection = sentinel1_filtering(collection, band, **kwargs)

        # Check if collection is empty
        collection_size = collection.size().getInfo()
        if collection_size == 0:
            print("Warning: No Sentinel-1 images found for the specified parameters")
            # Return base gif without sampling
            if mp4:
                gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
            return base_gif

        print(f"Found {collection_size} Sentinel-1 images for sampling")

        # Create time series
        ts_collection = create_timeseries(
            collection,
            start,
            end,
            roi,
            bands,
            frequency,
            reducer,
            True,  # drop_empty
            date_format,
            1,
            1,
        )

        # Check if time series is empty
        ts_size = ts_collection.size().getInfo()
        if ts_size == 0:
            print("Warning: No time series data generated")
            if mp4:
                gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
            return base_gif

        print(f"Generated {ts_size} time series images")

    except Exception as e:
        print(f"Error creating time series: {str(e)}")
        # Return base gif without sampling
        if mp4:
            gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
        return base_gif

    # Sample points from the time series
    sample_data = {}
    point_geometries = []

    if sample_points is not None and len(sample_points) > 0:
        try:
            for i, point in enumerate(sample_points):
                if sample_point_crs == "EPSG:4326":
                    geometry = ee.Geometry.Point([point[0], point[1]])
                else:
                    geometry = ee.Geometry.Point([point[0], point[1]], sample_point_crs)

                point_geometries.append(geometry)

                # Sample the time series at this point
                def sample_point(image):
                    sampled = image.sample(geometry, 30)
                    return sampled.first().set(
                        {
                            "system:time_start": image.get("system:time_start"),
                            "system:date": image.get("system:date"),
                        }
                    )

                sampled = ts_collection.map(sample_point)

                # Get the time series data with error handling
                try:
                    time_series = sampled.aggregate_array("system:time_start").getInfo()
                    values = sampled.aggregate_array(band).getInfo()
                    dates = sampled.aggregate_array("system:date").getInfo()

                    # Filter out null values
                    valid_data = [
                        (t, v, d)
                        for t, v, d in zip(time_series, values, dates)
                        if v is not None
                    ]

                    if valid_data:
                        time_series, values, dates = zip(*valid_data)

                        # Convert timestamps to datetime objects
                        datetimes = [
                            datetime.fromtimestamp(ts / 1000) for ts in time_series
                        ]

                        sample_data[f"Point_{i+1}"] = {
                            "dates": datetimes,
                            "values": list(values),
                            "date_strings": list(dates),
                            "color": marker_colors[i],
                            "geometry": geometry,
                        }

                        print(f"Point {i+1}: {len(values)} valid samples")
                    else:
                        print(f"Warning: No valid data for point {i+1}")

                except Exception as e:
                    print(f"Error sampling point {i+1}: {str(e)}")
                    continue

        except Exception as e:
            print(f"Error during point sampling: {str(e)}")
            sample_data = {}
    else:
        print("No sample points provided. Skipping sampling step.")

    # Add sample point markers to the base gif if requested
    if show_sample_markers and sample_points is not None and len(sample_points) > 0:
        try:
            # Get ROI bounds for coordinate conversion
            roi_bounds = roi.bounds().getInfo()["coordinates"][0]
            min_lon = min([coord[0] for coord in roi_bounds])
            max_lon = max([coord[0] for coord in roi_bounds])
            min_lat = min([coord[1] for coord in roi_bounds])
            max_lat = max([coord[1] for coord in roi_bounds])
            bounds = [min_lon, min_lat, max_lon, max_lat]

            # Add markers to the gif
            add_sample_markers_to_gif(
                base_gif,
                base_gif,
                sample_points,
                marker_colors,
                marker_size,
                marker_style,
                bounds,
                (
                    adjusted_dimensions
                    if "adjusted_dimensions" in locals()
                    else dimensions
                ),
            )
            print("Added sample markers to GIF")

        except Exception as e:
            print(f"Error adding markers to GIF: {str(e)}")

    # Create the time series chart if we have sample data
    if sample_data and len(sample_data) > 0:
        try:
            chart_frames = create_time_series_chart_frames(
                sample_data,
                chart_title,
                chart_ylabel,
                (
                    adjusted_dimensions
                    if "adjusted_dimensions" in locals()
                    else dimensions
                ),
                frames_per_second,
                chart_xlabel_format,
                chart_xlabel_interval,
            )

            # Combine gif and chart
            final_gif = combine_gif_with_chart(
                base_gif,
                chart_frames,
                chart_position,
                chart_size_ratio,
                spacer_width,
                frames_per_second,
                loop,
            )

            print("Created time series chart and combined with GIF")

        except Exception as e:
            print(f"Error creating chart: {str(e)}")
            final_gif = base_gif
    else:
        print("No sample data available. Returning map-only timelapse.")
        final_gif = base_gif

    # Handle MP4 conversion
    if mp4:
        gif_to_mp4(final_gif, final_gif.replace(".gif", ".mp4"))

    return final_gif


def add_sample_markers_to_gif(
    in_gif,
    out_gif,
    sample_points,
    marker_colors,
    marker_size,
    marker_style,
    roi_bounds,
    gif_dimensions,
):
    """Add sample point markers to a GIF.

    Args:
        in_gif (str): Path to input GIF file
        out_gif (str): Path to output GIF file
        sample_points (list): List of [lon, lat] coordinates
        marker_colors (list): List of colors for each marker
        marker_size (int): Size of markers in pixels
        marker_style (str): Style of markers ('cross', 'circle', 'square')
        roi_bounds (list): [min_lon, min_lat, max_lon, max_lat] bounds of the ROI
        gif_dimensions (int): Dimensions of the GIF
    """
    import io
    import warnings
    from PIL import Image, ImageDraw, ImageSequence
    import math

    warnings.simplefilter("ignore")

    in_gif = os.path.abspath(in_gif)
    out_gif = os.path.abspath(out_gif)

    if not os.path.exists(in_gif):
        raise FileNotFoundError(f"Input GIF file does not exist: {in_gif}")

    if not os.path.exists(os.path.dirname(out_gif)):
        os.makedirs(os.path.dirname(out_gif))

    try:
        # Open the GIF
        gif = Image.open(in_gif)

        # Get GIF properties
        gif_width, gif_height = gif.size

        # Convert sample points to pixel coordinates
        sample_points_pixel = []

        for i, point in enumerate(sample_points):
            lon, lat = point[0], point[1]

            # Convert geographic coordinates to pixel coordinates
            pixel_x, pixel_y = get_pixel_coordinates_from_geo(
                lon, lat, roi_bounds, gif_width, gif_height
            )

            sample_points_pixel.append(
                {
                    "x": pixel_x,
                    "y": pixel_y,
                    "color": marker_colors[i] if i < len(marker_colors) else "red",
                }
            )

        # Process each frame
        frames = []
        frame_count = 0

        try:
            while True:
                frame = gif.copy()
                frame = frame.convert("RGB")

                # Draw markers on the frame
                draw = ImageDraw.Draw(frame)

                for point in sample_points_pixel:
                    x, y = point["x"], point["y"]
                    color = point["color"]

                    # Draw marker based on style
                    if marker_style == "circle":
                        draw_circle_marker(draw, x, y, marker_size, color)
                    elif marker_style == "square":
                        draw_square_marker(draw, x, y, marker_size, color)
                    else:  # default to cross
                        draw_cross_marker(draw, x, y, marker_size, color)

                # Convert back to GIF frame format
                b = io.BytesIO()
                frame.save(b, format="GIF")
                frame = Image.open(b)
                frames.append(frame)

                # Move to next frame
                gif.seek(gif.tell() + 1)
                frame_count += 1

        except EOFError:
            # End of GIF frames
            pass

        # Save the new GIF with markers
        if frames:
            frames[0].save(
                out_gif,
                save_all=True,
                append_images=frames[1:],
                duration=gif.info.get("duration", 100),
                loop=gif.info.get("loop", 0),
                optimize=True,
            )

    except Exception as e:
        raise Exception(f"Error processing GIF: {str(e)}")


def draw_cross_marker(draw, x, y, size, color):
    """Draw a cross marker."""
    half_size = size // 2
    # Horizontal line
    draw.line([x - half_size, y, x + half_size, y], fill=color, width=3)
    # Vertical line
    draw.line([x, y - half_size, x, y + half_size], fill=color, width=3)
    # Add outline for better visibility
    draw.line([x - half_size, y, x + half_size, y], fill="white", width=1)
    draw.line([x, y - half_size, x, y + half_size], fill="white", width=1)


def draw_circle_marker(draw, x, y, size, color):
    """Draw a circle marker."""
    half_size = size // 2
    # Outer circle (outline)
    draw.ellipse(
        [x - half_size, y - half_size, x + half_size, y + half_size],
        outline="white",
        width=3,
    )
    # Inner circle (fill)
    draw.ellipse(
        [x - half_size + 2, y - half_size + 2, x + half_size - 2, y + half_size - 2],
        fill=color,
        outline=color,
    )


def draw_square_marker(draw, x, y, size, color):
    """Draw a square marker."""
    half_size = size // 2
    # Outer square (outline)
    draw.rectangle(
        [x - half_size, y - half_size, x + half_size, y + half_size],
        outline="white",
        width=3,
    )
    # Inner square (fill)
    draw.rectangle(
        [x - half_size + 2, y - half_size + 2, x + half_size - 2, y + half_size - 2],
        fill=color,
        outline=color,
    )


def get_pixel_coordinates_from_geo(lon, lat, roi_bounds, gif_width, gif_height):
    """Convert geographic coordinates to pixel coordinates.

    Args:
        lon (float): Longitude
        lat (float): Latitude
        roi_bounds (list): [min_lon, min_lat, max_lon, max_lat]
        gif_width (int): Width of GIF in pixels
        gif_height (int): Height of GIF in pixels

    Returns:
        tuple: (pixel_x, pixel_y)
    """
    min_lon, min_lat, max_lon, max_lat = roi_bounds

    # Linear transformation from geographic to pixel coordinates
    pixel_x = int(((lon - min_lon) / (max_lon - min_lon)) * gif_width)
    pixel_y = int(((max_lat - lat) / (max_lat - min_lat)) * gif_height)  # Flip Y axis

    # Ensure coordinates are within bounds
    pixel_x = max(0, min(gif_width - 1, pixel_x))
    pixel_y = max(0, min(gif_height - 1, pixel_y))

    return pixel_x, pixel_y


def create_time_series_chart_frames(
    sample_data,
    chart_title,
    chart_ylabel,
    dimensions,
    fps,
    xlabel_format="auto",
    xlabel_interval="auto",
):
    """Create frames for the time series chart with current time indicator."""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    from datetime import datetime
    import tempfile

    if not sample_data:
        return []

    # Get all unique dates across all points
    all_dates = set()
    for point_data in sample_data.values():
        all_dates.update(point_data["dates"])

    if not all_dates:
        return []

    sorted_dates = sorted(list(all_dates))

    # Create chart frames
    chart_frames = []
    temp_dir = tempfile.mkdtemp()

    # Calculate chart dimensions
    if isinstance(dimensions, str) and "x" in dimensions:
        width, height = map(int, dimensions.split("x"))
    else:
        width = height = int(dimensions) if isinstance(dimensions, int) else 768

    chart_width = int(width * 0.8)  # 80% of gif width
    chart_height = height

    try:
        for frame_idx, current_date in enumerate(sorted_dates):
            fig, ax = plt.subplots(
                figsize=(chart_width / 100, chart_height / 100), dpi=100
            )

            # Plot all time series
            for point_name, point_data in sample_data.items():
                if point_data["dates"] and point_data["values"]:
                    ax.plot(
                        point_data["dates"],
                        point_data["values"],
                        color=point_data["color"],
                        label=point_name,
                        linewidth=2,
                        marker="o",
                        markersize=4,
                    )

            # Add vertical line for current time
            ax.axvline(
                x=current_date, color="red", linestyle="--", linewidth=2, alpha=0.8
            )

            # Formatting
            ax.set_xlabel("Date", fontsize=10)
            ax.set_ylabel(chart_ylabel, fontsize=10)
            ax.set_title(chart_title, fontsize=12)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)

            # Format x-axis based on parameters or auto-detect
            date_range = (max(sorted_dates) - min(sorted_dates)).days

            if xlabel_format == "auto" or xlabel_interval == "auto":
                # Auto-detect based on data characteristics
                if date_range <= 30:  # Less than 1 month - likely daily/weekly data
                    format_str = "%m-%d"
                    if len(sorted_dates) <= 10:
                        # Few points, show all
                        locator = mdates.DayLocator(interval=max(1, date_range // 10))
                    else:
                        # Many points, show weekly
                        locator = mdates.WeekdayLocator(interval=1)
                elif date_range <= 90:  # Less than 3 months - likely weekly data
                    format_str = "%m-%d"
                    if len(sorted_dates) <= 15:
                        # Weekly data with few points
                        locator = mdates.WeekdayLocator(interval=1)
                    else:
                        # Weekly data with many points
                        locator = mdates.WeekdayLocator(
                            interval=max(1, len(sorted_dates) // 10)
                        )
                elif date_range <= 365:  # Less than 1 year - likely monthly data
                    format_str = "%Y-%m"
                    locator = mdates.MonthLocator(
                        interval=max(1, len(sorted_dates) // 8)
                    )
                else:  # More than 1 year - yearly data
                    format_str = "%Y"
                    locator = mdates.YearLocator()
            else:
                # Use manual settings
                format_str = xlabel_format if xlabel_format != "auto" else "%Y-%m-%d"

                if xlabel_interval == "day":
                    locator = mdates.DayLocator(
                        interval=max(1, len(sorted_dates) // 15)
                    )
                elif xlabel_interval == "week":
                    locator = mdates.WeekdayLocator(
                        interval=max(1, len(sorted_dates) // 10)
                    )
                elif xlabel_interval == "month":
                    locator = mdates.MonthLocator(
                        interval=max(1, len(sorted_dates) // 8)
                    )
                elif xlabel_interval == "year":
                    locator = mdates.YearLocator()
                else:
                    locator = mdates.WeekdayLocator(
                        interval=max(1, len(sorted_dates) // 10)
                    )

            ax.xaxis.set_major_formatter(mdates.DateFormatter(format_str))
            ax.xaxis.set_major_locator(locator)

            # Add minor ticks for better granularity on weekly data
            if date_range <= 90:
                ax.xaxis.set_minor_locator(mdates.DayLocator(interval=1))

            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)

            # Set consistent y-axis limits
            all_values = []
            for point_data in sample_data.values():
                all_values.extend([v for v in point_data["values"] if v is not None])

            if all_values:
                y_min, y_max = min(all_values), max(all_values)
                y_range = y_max - y_min
                if y_range > 0:
                    ax.set_ylim(y_min - y_range * 0.1, y_max + y_range * 0.1)
                else:
                    ax.set_ylim(y_min - 1, y_max + 1)

            plt.tight_layout()

            # Save frame
            frame_path = os.path.join(temp_dir, f"chart_frame_{frame_idx:04d}.png")
            plt.savefig(frame_path, dpi=100, bbox_inches="tight", facecolor="white")
            plt.close()

            chart_frames.append(frame_path)

    except Exception as e:
        print(f"Error creating chart frames: {str(e)}")
        # Clean up any created frames
        for frame_path in chart_frames:
            if os.path.exists(frame_path):
                os.remove(frame_path)
        return []

    return chart_frames


def combine_gif_with_chart(
    base_gif, chart_frames, chart_position, chart_size_ratio, spacer_width, fps, loop
):
    """Combine GIF with chart frames."""
    from PIL import Image, ImageDraw
    import tempfile

    # Open the base gif
    base_image = Image.open(base_gif)
    base_frames = []

    # Extract all frames from base gif
    try:
        while True:
            base_frames.append(base_image.copy())
            base_image.seek(base_image.tell() + 1)
    except EOFError:
        pass

    # Create combined frames
    combined_frames = []
    temp_dir = tempfile.mkdtemp()

    for i, base_frame in enumerate(base_frames):
        base_frame = base_frame.convert("RGB")

        # Get corresponding chart frame (cycle if needed)
        chart_idx = i % len(chart_frames) if chart_frames else 0

        if chart_frames:
            chart_frame = Image.open(chart_frames[chart_idx])
            chart_frame = chart_frame.convert("RGB")

            # Calculate dimensions
            base_width, base_height = base_frame.size
            chart_width, chart_height = chart_frame.size

            # Create combined image based on position
            if chart_position == "right":
                combined_width = base_width + spacer_width + chart_width
                combined_height = max(base_height, chart_height)
                combined_frame = Image.new(
                    "RGB", (combined_width, combined_height), "white"
                )
                combined_frame.paste(base_frame, (0, 0))
                combined_frame.paste(chart_frame, (base_width + spacer_width, 0))

            elif chart_position == "left":
                combined_width = chart_width + spacer_width + base_width
                combined_height = max(base_height, chart_height)
                combined_frame = Image.new(
                    "RGB", (combined_width, combined_height), "white"
                )
                combined_frame.paste(chart_frame, (0, 0))
                combined_frame.paste(base_frame, (chart_width + spacer_width, 0))

            elif chart_position == "bottom":
                combined_width = max(base_width, chart_width)
                combined_height = base_height + spacer_width + chart_height
                combined_frame = Image.new(
                    "RGB", (combined_width, combined_height), "white"
                )
                combined_frame.paste(base_frame, (0, 0))
                combined_frame.paste(chart_frame, (0, base_height + spacer_width))

            else:  # default to right
                combined_width = base_width + spacer_width + chart_width
                combined_height = max(base_height, chart_height)
                combined_frame = Image.new(
                    "RGB", (combined_width, combined_height), "white"
                )
                combined_frame.paste(base_frame, (0, 0))
                combined_frame.paste(chart_frame, (base_width + spacer_width, 0))

        else:
            combined_frame = base_frame

        combined_frames.append(combined_frame)

    # Save combined gif
    output_path = base_gif.replace(".gif", "_with_chart.gif")

    if combined_frames:
        combined_frames[0].save(
            output_path,
            save_all=True,
            append_images=combined_frames[1:],
            duration=int(1000 / fps),
            loop=loop,
            optimize=True,
        )

    # Clean up chart frames
    for frame_path in chart_frames:
        if os.path.exists(frame_path):
            os.remove(frame_path)

    return output_path


def sentinel2_timelapse_with_samples(
    roi,
    out_gif=None,
    start_year=2015,
    end_year=None,
    start_date="06-10",
    end_date="09-20",
    bands=["NIR", "Red", "Green"],
    frequency="year",
    reducer="median",
    date_format=None,
    palette=None,
    vis_params=None,
    dimensions=768,
    frames_per_second=10,
    crs="EPSG:3857",
    mask_cloud=True,
    cloud_pct=30,
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    add_colorbar=False,
    colorbar_width=6.0,
    colorbar_height=0.4,
    colorbar_label=None,
    colorbar_label_size=12,
    colorbar_label_weight="normal",
    colorbar_tick_size=10,
    colorbar_bg_color=None,
    colorbar_orientation="horizontal",
    colorbar_dpi="figure",
    colorbar_xy=None,
    colorbar_size=(300, 300),
    loop=0,
    mp4=False,
    fading=False,
    sample_points=None,
    sample_point_crs="EPSG:4326",
    marker_colors=None,
    marker_size=50,
    marker_style="cross",
    show_sample_markers=True,
    chart_title="Sentinel-2 Time Series",
    chart_ylabel="Reflectance",
    chart_position="right",
    chart_size_ratio=0.7,
    spacer_width=20,
    chart_xlabel_format="auto",
    chart_xlabel_interval="auto",
    sample_bands=None,
    chart_band_labels=None,
    indices=None,
    index_vis_params=None,
    **kwargs,
):
    """Create a Sentinel-2 timelapse with optional sample points and time series chart.

    Args:
        roi (ee.Geometry): The region to use to filter the collection of images.
        out_gif (str): The output gif file path. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 2015.
        end_year (int, optional): Ending year for the timelapse. Defaults to the current year.
        start_date (str, optional): Starting date (month-day) each year. Defaults to '06-10'.
        end_date (str, optional): Ending date (month-day) each year. Defaults to '09-20'.
        bands (list, optional): Three bands for visualization. Defaults to ["NIR", "Red", "Green"].
        frequency (str, optional): The frequency of the timeseries. Defaults to 'year'.
        reducer (str, optional): The reducer to use. Defaults to 'median'.
        date_format (str, optional): Date format pattern. Defaults to None.
        palette (str, optional): Color palette for single-band visualization. Defaults to None.
        vis_params (dict, optional): Visualization parameters. Defaults to None.
        dimensions (int, optional): Maximum dimensions of the thumbnail. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        crs (str, optional): Coordinate reference system. Defaults to "EPSG:3857".
        mask_cloud (bool, optional): Whether to mask clouds. Defaults to True.
        cloud_pct (int, optional): Maximum cloud percentage. Defaults to 30.
        overlay_data (optional): Administrative boundary overlay. Defaults to None.
        overlay_color (str, optional): Color for overlay data. Defaults to 'black'.
        overlay_width (int, optional): Width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Position of the title. Defaults to ("2%", "90%").
        add_text (bool, optional): Whether to add animated text. Defaults to True.
        text_xy (tuple, optional): Position of the text. Defaults to ("2%", "2%").
        text_sequence (optional): Text to be drawn. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. Defaults to 'white'.
        add_progress_bar (bool, optional): Whether to add progress bar. Defaults to True.
        progress_bar_color (str, optional): Color for progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of progress bar. Defaults to 5.
        add_colorbar (bool, optional): Whether to add colorbar. Defaults to False.
        colorbar_width (float, optional): Width of colorbar. Defaults to 6.0.
        colorbar_height (float, optional): Height of colorbar. Defaults to 0.4.
        colorbar_label (str, optional): Label for colorbar. Defaults to None.
        colorbar_label_size (int, optional): Font size for colorbar label. Defaults to 12.
        colorbar_label_weight (str, optional): Font weight for colorbar label. Defaults to 'normal'.
        colorbar_tick_size (int, optional): Font size for colorbar ticks. Defaults to 10.
        colorbar_bg_color (str, optional): Background color for colorbar. Defaults to None.
        colorbar_orientation (str, optional): Orientation of colorbar. Defaults to 'horizontal'.
        colorbar_dpi (str, optional): DPI for colorbar. Defaults to 'figure'.
        colorbar_xy (tuple, optional): Position of colorbar. Defaults to None.
        colorbar_size (tuple, optional): Size of colorbar. Defaults to (300, 300).
        loop (int, optional): Number of animation loops. Defaults to 0.
        mp4 (bool, optional): Whether to create mp4 file. Defaults to False.
        fading (bool, optional): Whether to add fading effect. Defaults to False.
        sample_points (list, optional): List of [lon, lat] coordinates for sampling (max 5 points). Defaults to None.
        sample_point_crs (str, optional): CRS for sample points. Defaults to "EPSG:4326".
        marker_colors (list, optional): Colors for markers. Defaults to None (uses default colors).
        marker_size (int, optional): Size of markers. Defaults to 50.
        marker_style (str, optional): Style of markers ('cross', 'circle', 'square'). Defaults to 'cross'.
        show_sample_markers (bool, optional): Whether to show markers on map. Defaults to True.
        chart_title (str, optional): Title for the time series chart. Defaults to "Sentinel-2 Time Series".
        chart_ylabel (str, optional): Y-axis label for chart. Defaults to "Reflectance".
        chart_position (str, optional): Position of chart ('right', 'left', 'bottom'). Defaults to 'right'.
        chart_size_ratio (float, optional): Size ratio of chart to gif. Defaults to 0.7.
        spacer_width (int, optional): Width of spacer between gif and chart. Defaults to 20.
        chart_xlabel_format (str, optional): Format for x-axis labels ('auto', '%Y-%m', '%m-%d', '%Y-%m-%d'). Defaults to 'auto'.
        chart_xlabel_interval (str, optional): Interval for x-axis labels ('auto', 'day', 'week', 'month', 'year'). Defaults to 'auto'.
        sample_bands (list, optional): Which bands to sample for the chart. Defaults to first band only.
        chart_band_labels (dict, optional): Custom labels for bands in chart. Defaults to None.
        indices (list, optional): List of indices to calculate ['NDVI', 'EVI', 'NDWI', 'NDBI', 'MNDWI', 'NBR']. Defaults to None.
        index_vis_params (dict, optional): Visualization parameters for indices. Defaults to None.
        **kwargs: Additional arguments for create_timeseries().

    Returns:
        str: File path to the output GIF with optional chart.
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    from datetime import datetime, date
    import tempfile
    import math

    # Handle indices parameter
    if indices is not None:
        if not isinstance(indices, list):
            indices = [indices]

        # Validate indices
        valid_indices = [
            "NDVI",
            "EVI",
            "NDWI",
            "MNDWI",
            "NDBI",
            "NBR",
            "SAVI",
            "GNDVI",
            "NDRE",
            "CIRE",
        ]
        for idx in indices:
            if idx not in valid_indices:
                raise ValueError(
                    f"Index '{idx}' not supported. Valid indices: {valid_indices}"
                )

        # If using indices, update defaults
        if sample_bands is None:
            sample_bands = indices[:1]  # Default to first index

        if chart_ylabel == "Reflectance":
            chart_ylabel = "Index Value"

        # Set up index visualization if not provided
        if index_vis_params is None:
            index_vis_params = get_default_index_vis_params()

        # For single index visualization, set up palette and vis_params
        if len(indices) == 1 and vis_params is None:
            index_name = indices[0]
            if palette is None and index_name in index_vis_params:
                palette = index_vis_params[index_name]["palette"]
                vis_params = {
                    "min": index_vis_params[index_name]["min"],
                    "max": index_vis_params[index_name]["max"],
                    "palette": palette,
                }

        # If visualizing an index, update bands for visualization
        if len(indices) == 1 and len(bands) == 3:
            # For single index, use that index for visualization
            bands = indices

    # Validate sample points
    if sample_points is not None:
        if not isinstance(sample_points, list):
            raise ValueError("sample_points must be a list of [lon, lat] coordinates")
        if len(sample_points) > 5:
            raise ValueError("Maximum 5 sample points are supported")
        if len(sample_points) == 0:
            sample_points = None

    # Set default marker colors if not provided
    if sample_points is not None and marker_colors is None:
        marker_colors = ["red", "blue", "green", "orange", "purple"][
            : len(sample_points)
        ]
    elif sample_points is not None and len(marker_colors) < len(sample_points):
        default_colors = ["red", "blue", "green", "orange", "purple"]
        marker_colors.extend(default_colors[len(marker_colors) : len(sample_points)])

    # Set default sample bands if not provided
    if sample_bands is None:
        sample_bands = [bands[0]] if bands else ["B4"]  # Default to first band or Red

    # Set default chart band labels
    if chart_band_labels is None:
        chart_band_labels = {
            "B2": "Blue",
            "B3": "Green",
            "B4": "Red",
            "B5": "Red Edge 1",
            "B6": "Red Edge 2",
            "B7": "Red Edge 3",
            "B8": "NIR",
            "B8A": "Red Edge 4",
            "B11": "SWIR1",
            "B12": "SWIR2",
        }
        # Add index labels
        index_labels = get_index_chart_labels()
        chart_band_labels.update(index_labels)

    # Adjust dimensions to avoid Earth Engine limits
    if isinstance(roi, ee.Geometry):
        roi_bounds = roi.bounds().getInfo()["coordinates"][0]
        min_lon = min([coord[0] for coord in roi_bounds])
        max_lon = max([coord[0] for coord in roi_bounds])
        min_lat = min([coord[1] for coord in roi_bounds])
        max_lat = max([coord[1] for coord in roi_bounds])

        # Calculate aspect ratio and adjust dimensions
        lon_range = max_lon - min_lon
        lat_range = max_lat - min_lat
        aspect_ratio = lon_range / lat_range if lat_range > 0 else 1

        max_pixels = 26214400  # Earth Engine limit

        if isinstance(dimensions, int):
            if aspect_ratio > 1:
                width = min(dimensions, int(math.sqrt(max_pixels * aspect_ratio)))
                height = int(width / aspect_ratio)
            else:
                height = min(dimensions, int(math.sqrt(max_pixels / aspect_ratio)))
                width = int(height * aspect_ratio)

            width = max(256, width)
            height = max(256, height)

            if width * height > max_pixels:
                scale_factor = math.sqrt(max_pixels / (width * height))
                width = int(width * scale_factor)
                height = int(height * scale_factor)

            adjusted_dimensions = f"{width}x{height}"
        else:
            adjusted_dimensions = dimensions

        print(f"Adjusted dimensions: {adjusted_dimensions}")
    else:
        adjusted_dimensions = dimensions

    # Create the base timelapse
    try:
        # If using indices, we need to create a custom timelapse that includes index calculation
        if indices is not None:
            base_gif = create_sentinel2_index_timelapse(
                roi=roi,
                out_gif=out_gif,
                start_year=start_year,
                end_year=end_year,
                start_date=start_date,
                end_date=end_date,
                bands=bands,
                indices=indices,
                vis_params=vis_params,
                dimensions=adjusted_dimensions,
                frames_per_second=frames_per_second,
                crs=crs,
                mask_cloud=mask_cloud,
                cloud_pct=cloud_pct,
                overlay_data=overlay_data,
                overlay_color=overlay_color,
                overlay_width=overlay_width,
                overlay_opacity=overlay_opacity,
                frequency=frequency,
                reducer=reducer,
                date_format=date_format,
                title=title,
                title_xy=title_xy,
                add_text=add_text,
                text_xy=text_xy,
                text_sequence=text_sequence,
                font_type=font_type,
                font_size=font_size,
                font_color=font_color,
                add_progress_bar=add_progress_bar,
                progress_bar_color=progress_bar_color,
                progress_bar_height=progress_bar_height,
                add_colorbar=add_colorbar,
                colorbar_width=colorbar_width,
                colorbar_height=colorbar_height,
                colorbar_label=colorbar_label,
                colorbar_label_size=colorbar_label_size,
                colorbar_label_weight=colorbar_label_weight,
                colorbar_tick_size=colorbar_tick_size,
                colorbar_bg_color=colorbar_bg_color,
                colorbar_orientation=colorbar_orientation,
                colorbar_dpi=colorbar_dpi,
                colorbar_xy=colorbar_xy,
                colorbar_size=colorbar_size,
                loop=loop,
                fading=fading,
                **kwargs,
            )
        else:
            # Use standard Sentinel-2 timelapse
            base_gif = sentinel2_timelapse(
                roi=roi,
                out_gif=out_gif,
                start_year=start_year,
                end_year=end_year,
                start_date=start_date,
                end_date=end_date,
                bands=bands,
                vis_params=vis_params,
                dimensions=adjusted_dimensions,
                frames_per_second=frames_per_second,
                crs=crs,
                apply_fmask=mask_cloud,
                cloud_pct=cloud_pct,
                overlay_data=overlay_data,
                overlay_color=overlay_color,
                overlay_width=overlay_width,
                overlay_opacity=overlay_opacity,
                frequency=frequency,
                date_format=date_format,
                title=title,
                title_xy=title_xy,
                add_text=add_text,
                text_xy=text_xy,
                text_sequence=text_sequence,
                font_type=font_type,
                font_size=font_size,
                font_color=font_color,
                add_progress_bar=add_progress_bar,
                progress_bar_color=progress_bar_color,
                progress_bar_height=progress_bar_height,
                loop=loop,
                mp4=False,
                fading=fading,
                **kwargs,
            )
    except Exception as e:
        print(f"Error creating base timelapse: {str(e)}")
        raise e

    # Check if base GIF was created successfully
    if not os.path.exists(base_gif):
        raise FileNotFoundError(f"Base timelapse GIF was not created: {base_gif}")

    # If no sample points, return the base gif (map only)
    if sample_points is None or len(sample_points) == 0:
        print("No sample points provided. Returning map-only timelapse.")
        if mp4:
            gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
        return base_gif

    # Get the Sentinel-2 time series for sampling
    if end_year is None:
        end_year = date.today().year

    start = f"{start_year}-{start_date}"
    end = f"{end_year}-{end_date}"

    # Create collection with error handling
    try:
        # Map band names to Sentinel-2 band names
        allowed_bands = {
            "Blue": "B2",
            "Green": "B3",
            "Red": "B4",
            "Red Edge 1": "B5",
            "Red Edge 2": "B6",
            "Red Edge 3": "B7",
            "NIR": "B8",
            "Red Edge 4": "B8A",
            "SWIR1": "B11",
            "SWIR2": "B12",
            "QA60": "QA60",
        }

        # Convert sample band names if needed (include indices)
        s2_sample_bands = []
        for band in sample_bands:
            if band in allowed_bands:
                s2_sample_bands.append(allowed_bands[band])
            elif band in [
                "NDVI",
                "EVI",
                "NDWI",
                "MNDWI",
                "NDBI",
                "NBR",
                "SAVI",
                "GNDVI",
                "NDRE",
                "CIRE",
            ]:
                s2_sample_bands.append(band)  # Keep index names as-is
            else:
                s2_sample_bands.append(band)

        # Create time series - if using indices, we need to add index calculation
        if indices is not None:
            # Create base time series first
            base_ts_collection = sentinel2_timeseries(
                roi,
                start_year,
                end_year,
                start_date,
                end_date,
                None,  # Get all bands first
                mask_cloud,
                cloud_pct,
                frequency,
                reducer,
                True,  # drop_empty
                date_format,
                1,
                1,
            )

            # Add indices to each image
            ts_collection = base_ts_collection.map(calculate_sentinel2_indices)

            # Select only the bands we need for sampling
            ts_collection = ts_collection.select(s2_sample_bands)
        else:
            # Standard time series without indices
            ts_collection = sentinel2_timeseries(
                roi,
                start_year,
                end_year,
                start_date,
                end_date,
                s2_sample_bands,
                mask_cloud,
                cloud_pct,
                frequency,
                reducer,
                True,  # drop_empty
                date_format,
                1,
                1,
            )

        # Check if time series is empty
        ts_size = ts_collection.size().getInfo()
        if ts_size == 0:
            print("Warning: No time series data generated")
            if mp4:
                gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
            return base_gif

        print(f"Generated {ts_size} time series images")

    except Exception as e:
        print(f"Error creating time series: {str(e)}")
        # Return base gif without sampling
        if mp4:
            gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
        return base_gif

    # Sample points from the time series
    sample_data = {}
    point_geometries = []

    if sample_points is not None and len(sample_points) > 0:
        try:
            for i, point in enumerate(sample_points):
                if sample_point_crs == "EPSG:4326":
                    geometry = ee.Geometry.Point([point[0], point[1]])
                else:
                    geometry = ee.Geometry.Point([point[0], point[1]], sample_point_crs)

                point_geometries.append(geometry)

                # Sample the time series at this point for each band
                for band_idx, band in enumerate(s2_sample_bands):

                    def sample_point_band(image):
                        sampled = image.select(band).sample(geometry, 30)
                        return sampled.first().set(
                            {
                                "system:time_start": image.get("system:time_start"),
                                "system:date": image.get("system:date"),
                            }
                        )

                    sampled = ts_collection.map(sample_point_band)

                    # Get the time series data with error handling
                    try:
                        time_series = sampled.aggregate_array(
                            "system:time_start"
                        ).getInfo()
                        values = sampled.aggregate_array(band).getInfo()
                        dates = sampled.aggregate_array("system:date").getInfo()

                        # Filter out null values
                        valid_data = [
                            (t, v, d)
                            for t, v, d in zip(time_series, values, dates)
                            if v is not None
                        ]

                        if valid_data:
                            time_series, values, dates = zip(*valid_data)

                            # Convert timestamps to datetime objects
                            datetimes = [
                                datetime.fromtimestamp(ts / 1000) for ts in time_series
                            ]

                            # Create unique key for point and band combination
                            point_band_key = f"Point_{i+1}_{band}"
                            if len(s2_sample_bands) == 1:
                                point_band_key = f"Point_{i+1}"

                            # Get display name for band
                            band_display = chart_band_labels.get(band, band)
                            if len(s2_sample_bands) > 1:
                                label = f"Point {i+1} ({band_display})"
                            else:
                                label = f"Point {i+1}"

                            # Color assignment for multi-band sampling
                            if len(s2_sample_bands) > 1:
                                base_color = (
                                    marker_colors[i]
                                    if i < len(marker_colors)
                                    else "red"
                                )
                                # Modify color for different bands
                                if band_idx == 0:
                                    color = base_color
                                elif band_idx == 1:
                                    color = (
                                        f"dark{base_color}"
                                        if base_color != "red"
                                        else "darkred"
                                    )
                                else:
                                    color = (
                                        f"light{base_color}"
                                        if base_color != "red"
                                        else "lightcoral"
                                    )
                            else:
                                color = (
                                    marker_colors[i]
                                    if i < len(marker_colors)
                                    else "red"
                                )

                            sample_data[point_band_key] = {
                                "dates": datetimes,
                                "values": list(values),
                                "date_strings": list(dates),
                                "color": color,
                                "geometry": geometry,
                                "label": label,
                                "band": band,
                                "point_idx": i,
                            }

                            print(f"Point {i+1} ({band}): {len(values)} valid samples")
                        else:
                            print(f"Warning: No valid data for point {i+1} ({band})")

                    except Exception as e:
                        print(f"Error sampling point {i+1} ({band}): {str(e)}")
                        continue

        except Exception as e:
            print(f"Error during point sampling: {str(e)}")
            sample_data = {}
    else:
        print("No sample points provided. Skipping sampling step.")

    # Add sample point markers to the base gif if requested
    if show_sample_markers and sample_points is not None and len(sample_points) > 0:
        try:
            # Get ROI bounds for coordinate conversion
            roi_bounds = roi.bounds().getInfo()["coordinates"][0]
            min_lon = min([coord[0] for coord in roi_bounds])
            max_lon = max([coord[0] for coord in roi_bounds])
            min_lat = min([coord[1] for coord in roi_bounds])
            max_lat = max([coord[1] for coord in roi_bounds])
            bounds = [min_lon, min_lat, max_lon, max_lat]

            # Add markers to the gif
            add_sample_markers_to_gif(
                base_gif,
                base_gif,
                sample_points,
                marker_colors,
                marker_size,
                marker_style,
                bounds,
                (
                    adjusted_dimensions
                    if "adjusted_dimensions" in locals()
                    else dimensions
                ),
            )
            print("Added sample markers to GIF")

        except Exception as e:
            print(f"Error adding markers to GIF: {str(e)}")

    # Create the time series chart if we have sample data
    if sample_data and len(sample_data) > 0:
        try:
            chart_frames = create_s2_time_series_chart_frames(
                sample_data,
                chart_title,
                chart_ylabel,
                (
                    adjusted_dimensions
                    if "adjusted_dimensions" in locals()
                    else dimensions
                ),
                frames_per_second,
                chart_xlabel_format,
                chart_xlabel_interval,
            )

            # Combine gif and chart
            final_gif = combine_gif_with_chart(
                base_gif,
                chart_frames,
                chart_position,
                chart_size_ratio,
                spacer_width,
                frames_per_second,
                loop,
            )

            print("Created time series chart and combined with GIF")

        except Exception as e:
            print(f"Error creating chart: {str(e)}")
            final_gif = base_gif
    else:
        print("No sample data available. Returning map-only timelapse.")
        final_gif = base_gif

    # Handle MP4 conversion
    if mp4:
        gif_to_mp4(final_gif, final_gif.replace(".gif", ".mp4"))

    return final_gif


def calculate_sentinel2_indices(image):
    """Calculate common vegetation and water indices for Sentinel-2 images.

    Args:
        image (ee.Image): Sentinel-2 image with bands B2, B3, B4, B5, B6, B7, B8, B8A, B11, B12

    Returns:
        ee.Image: Image with added index bands
    """
    # Normalized Difference Vegetation Index
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")

    # Enhanced Vegetation Index
    evi = image.expression(
        "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
        {
            "NIR": image.select("B8"),
            "RED": image.select("B4"),
            "BLUE": image.select("B2"),
        },
    ).rename("EVI")

    # Normalized Difference Water Index
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")

    # Modified Normalized Difference Water Index
    mndwi = image.normalizedDifference(["B3", "B11"]).rename("MNDWI")

    # Normalized Difference Built-up Index
    ndbi = image.normalizedDifference(["B11", "B8"]).rename("NDBI")

    # Normalized Burn Ratio
    nbr = image.normalizedDifference(["B8", "B12"]).rename("NBR")

    # Soil Adjusted Vegetation Index
    savi = image.expression(
        "((NIR - RED) / (NIR + RED + 0.5)) * (1.5)",
        {"NIR": image.select("B8"), "RED": image.select("B4")},
    ).rename("SAVI")

    # Green Normalized Difference Vegetation Index
    gndvi = image.normalizedDifference(["B8", "B3"]).rename("GNDVI")

    # Normalized Difference Red Edge
    ndre = image.normalizedDifference(["B8", "B5"]).rename("NDRE")

    # Chlorophyll Index Red Edge
    cire = image.expression(
        "(NIR / RE1) - 1", {"NIR": image.select("B8"), "RE1": image.select("B5")}
    ).rename("CIRE")

    return image.addBands([ndvi, evi, ndwi, mndwi, ndbi, nbr, savi, gndvi, ndre, cire])


def get_default_index_vis_params():
    """Get default visualization parameters for different indices."""
    return {
        "NDVI": {
            "min": -0.1,
            "max": 1,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "EVI": {
            "min": -0.2,
            "max": 0.8,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "NDWI": {
            "min": -0.3,
            "max": 0.8,
            "palette": ["#8b4513", "#daa520", "#ffffbf", "#87ceeb", "#0000ff"],
        },
        "MNDWI": {
            "min": -0.3,
            "max": 0.8,
            "palette": ["#8b4513", "#daa520", "#ffffbf", "#87ceeb", "#0000ff"],
        },
        "NDBI": {
            "min": -0.5,
            "max": 0.5,
            "palette": ["#0000ff", "#87ceeb", "#ffffbf", "#daa520", "#8b4513"],
        },
        "NBR": {
            "min": -0.5,
            "max": 0.8,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "SAVI": {
            "min": -0.2,
            "max": 0.8,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "GNDVI": {
            "min": -0.2,
            "max": 0.8,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "NDRE": {
            "min": -0.2,
            "max": 0.6,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "CIRE": {
            "min": 0,
            "max": 5,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
    }


def get_index_chart_labels():
    """Get chart labels for different indices."""
    return {
        "NDVI": "NDVI",
        "EVI": "EVI",
        "NDWI": "NDWI",
        "MNDWI": "MNDWI",
        "NDBI": "NDBI",
        "NBR": "NBR",
        "SAVI": "SAVI",
        "GNDVI": "GNDVI",
        "NDRE": "NDRE",
        "CIRE": "CIre",
    }


def create_sentinel2_index_timelapse(
    roi,
    out_gif,
    start_year,
    end_year,
    start_date,
    end_date,
    bands,
    indices,
    vis_params,
    dimensions,
    frames_per_second,
    crs,
    mask_cloud,
    cloud_pct,
    overlay_data,
    overlay_color,
    overlay_width,
    overlay_opacity,
    frequency,
    reducer,
    date_format,
    title,
    title_xy,
    add_text,
    text_xy,
    text_sequence,
    font_type,
    font_size,
    font_color,
    add_progress_bar,
    progress_bar_color,
    progress_bar_height,
    add_colorbar,
    colorbar_width,
    colorbar_height,
    colorbar_label,
    colorbar_label_size,
    colorbar_label_weight,
    colorbar_tick_size,
    colorbar_bg_color,
    colorbar_orientation,
    colorbar_dpi,
    colorbar_xy,
    colorbar_size,
    loop,
    fading,
    **kwargs,
):
    """Create a Sentinel-2 timelapse with indices."""
    import datetime

    if end_year is None:
        end_year = datetime.datetime.now().year

    start = f"{start_year}-{start_date}"
    end = f"{end_year}-{end_date}"

    # Create time series with indices
    base_ts_collection = sentinel2_timeseries(
        roi,
        start_year,
        end_year,
        start_date,
        end_date,
        None,  # Get all bands first
        mask_cloud,
        cloud_pct,
        frequency,
        reducer,
        True,  # drop_empty
        date_format,
        1,
        1,
    )

    # Add indices to each image
    ts_collection = base_ts_collection.map(calculate_sentinel2_indices)

    # Use create_timelapse with the index collection
    return create_timelapse(
        ts_collection,
        start,
        end,
        roi,
        bands,
        frequency,
        reducer,
        date_format,
        out_gif,
        None,
        vis_params,
        dimensions,
        frames_per_second,
        crs,
        overlay_data,
        overlay_color,
        overlay_width,
        overlay_opacity,
        title,
        title_xy,
        add_text,
        text_xy,
        text_sequence,
        font_type,
        font_size,
        font_color,
        add_progress_bar,
        progress_bar_color,
        progress_bar_height,
        add_colorbar,
        colorbar_width,
        colorbar_height,
        colorbar_label,
        colorbar_label_size,
        colorbar_label_weight,
        colorbar_tick_size,
        colorbar_bg_color,
        colorbar_orientation,
        colorbar_dpi,
        colorbar_xy,
        colorbar_size,
        loop,
        False,
        fading,
        1,
        1,
    )


def create_s2_time_series_chart_frames(
    sample_data,
    chart_title,
    chart_ylabel,
    dimensions,
    fps,
    xlabel_format="auto",
    xlabel_interval="auto",
):
    """Create frames for the Sentinel-2 time series chart with current time indicator.

    Args:
        sample_data (dict): Dictionary containing sample data for each point/band combination
        chart_title (str): Title for the chart
        chart_ylabel (str): Y-axis label
        dimensions (int/str): Dimensions for the chart
        fps (int): Frames per second
        xlabel_format (str): Format for x-axis labels
        xlabel_interval (str): Interval for x-axis labels

    Returns:
        list: List of paths to chart frame images
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    from datetime import datetime
    import tempfile

    if not sample_data:
        return []

    # Get all unique dates across all points/bands
    all_dates = set()
    for point_data in sample_data.values():
        all_dates.update(point_data["dates"])

    if not all_dates:
        return []

    sorted_dates = sorted(list(all_dates))

    # Create chart frames
    chart_frames = []
    temp_dir = tempfile.mkdtemp()

    # Calculate chart dimensions
    if isinstance(dimensions, str) and "x" in dimensions:
        width, height = map(int, dimensions.split("x"))
    else:
        width = height = int(dimensions) if isinstance(dimensions, int) else 768

    chart_width = int(width * 0.8)  # 80% of gif width
    chart_height = height

    try:
        for frame_idx, current_date in enumerate(sorted_dates):
            fig, ax = plt.subplots(
                figsize=(chart_width / 100, chart_height / 100), dpi=100
            )

            # Plot all time series
            for point_key, point_data in sample_data.items():
                if point_data["dates"] and point_data["values"]:
                    # Use custom label if available, otherwise use point_key
                    label = point_data.get("label", point_key)

                    ax.plot(
                        point_data["dates"],
                        point_data["values"],
                        color=point_data["color"],
                        label=label,
                        linewidth=2,
                        marker="o",
                        markersize=4,
                    )

            # Add vertical line for current time
            ax.axvline(
                x=current_date, color="red", linestyle="--", linewidth=2, alpha=0.8
            )

            # Formatting
            ax.set_xlabel("Date", fontsize=10)
            ax.set_ylabel(chart_ylabel, fontsize=10)
            ax.set_title(chart_title, fontsize=12)
            ax.legend(fontsize=8, loc="upper left")
            ax.grid(True, alpha=0.3)

            # Format x-axis based on parameters or auto-detect
            date_range = (max(sorted_dates) - min(sorted_dates)).days

            if xlabel_format == "auto" or xlabel_interval == "auto":
                # Auto-detect based on data characteristics
                if date_range <= 30:  # Less than 1 month
                    format_str = "%m-%d"
                    if len(sorted_dates) <= 10:
                        locator = mdates.DayLocator(interval=max(1, date_range // 10))
                    else:
                        locator = mdates.WeekdayLocator(interval=1)
                elif date_range <= 90:  # Less than 3 months
                    format_str = "%m-%d"
                    if len(sorted_dates) <= 15:
                        locator = mdates.WeekdayLocator(interval=1)
                    else:
                        locator = mdates.WeekdayLocator(
                            interval=max(1, len(sorted_dates) // 10)
                        )
                elif date_range <= 365:  # Less than 1 year
                    format_str = "%Y-%m"
                    locator = mdates.MonthLocator(
                        interval=max(1, len(sorted_dates) // 8)
                    )
                else:  # More than 1 year
                    format_str = "%Y"
                    locator = mdates.YearLocator()
            else:
                # Use manual settings
                format_str = xlabel_format if xlabel_format != "auto" else "%Y-%m-%d"

                if xlabel_interval == "day":
                    locator = mdates.DayLocator(
                        interval=max(1, len(sorted_dates) // 15)
                    )
                elif xlabel_interval == "week":
                    locator = mdates.WeekdayLocator(
                        interval=max(1, len(sorted_dates) // 10)
                    )
                elif xlabel_interval == "month":
                    locator = mdates.MonthLocator(
                        interval=max(1, len(sorted_dates) // 8)
                    )
                elif xlabel_interval == "year":
                    locator = mdates.YearLocator()
                else:
                    locator = mdates.WeekdayLocator(
                        interval=max(1, len(sorted_dates) // 10)
                    )

            ax.xaxis.set_major_formatter(mdates.DateFormatter(format_str))
            ax.xaxis.set_major_locator(locator)

            # Add minor ticks for better granularity
            if date_range <= 90:
                ax.xaxis.set_minor_locator(mdates.DayLocator(interval=1))

            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)

            # Set consistent y-axis limits
            all_values = []
            for point_data in sample_data.values():
                all_values.extend([v for v in point_data["values"] if v is not None])

            if all_values:
                y_min, y_max = min(all_values), max(all_values)
                y_range = y_max - y_min
                if y_range > 0:
                    ax.set_ylim(y_min - y_range * 0.1, y_max + y_range * 0.1)
                else:
                    ax.set_ylim(y_min - 0.01, y_max + 0.01)

            plt.tight_layout()

            # Save frame
            frame_path = os.path.join(temp_dir, f"chart_frame_{frame_idx:04d}.png")
            plt.savefig(frame_path, dpi=100, bbox_inches="tight", facecolor="white")
            plt.close()

            chart_frames.append(frame_path)

    except Exception as e:
        print(f"Error creating chart frames: {str(e)}")
        # Clean up any created frames
        for frame_path in chart_frames:
            if os.path.exists(frame_path):
                os.remove(frame_path)
        return []

    return chart_frames


def add_sample_markers_to_gif(
    in_gif,
    out_gif,
    sample_points,
    marker_colors,
    marker_size,
    marker_style,
    roi_bounds,
    gif_dimensions,
):
    """Add sample point markers to a GIF.

    Args:
        in_gif (str): Path to input GIF file
        out_gif (str): Path to output GIF file
        sample_points (list): List of [lon, lat] coordinates
        marker_colors (list): List of colors for each marker
        marker_size (int): Size of markers in pixels
        marker_style (str): Style of markers ('cross', 'circle', 'square')
        roi_bounds (list): [min_lon, min_lat, max_lon, max_lat] bounds of the ROI
        gif_dimensions (int): Dimensions of the GIF
    """
    import io
    import warnings
    from PIL import Image, ImageDraw, ImageSequence
    import math

    warnings.simplefilter("ignore")

    in_gif = os.path.abspath(in_gif)
    out_gif = os.path.abspath(out_gif)

    if not os.path.exists(in_gif):
        raise FileNotFoundError(f"Input GIF file does not exist: {in_gif}")

    if not os.path.exists(os.path.dirname(out_gif)):
        os.makedirs(os.path.dirname(out_gif))

    try:
        # Open the GIF
        gif = Image.open(in_gif)

        # Get GIF properties
        gif_width, gif_height = gif.size

        # Convert sample points to pixel coordinates
        sample_points_pixel = []

        for i, point in enumerate(sample_points):
            lon, lat = point[0], point[1]

            # Convert geographic coordinates to pixel coordinates
            pixel_x, pixel_y = get_pixel_coordinates_from_geo(
                lon, lat, roi_bounds, gif_width, gif_height
            )

            sample_points_pixel.append(
                {
                    "x": pixel_x,
                    "y": pixel_y,
                    "color": marker_colors[i] if i < len(marker_colors) else "red",
                }
            )

        # Process each frame
        frames = []
        frame_count = 0

        try:
            while True:
                frame = gif.copy()
                frame = frame.convert("RGB")

                # Draw markers on the frame
                draw = ImageDraw.Draw(frame)

                for point in sample_points_pixel:
                    x, y = point["x"], point["y"]
                    color = point["color"]

                    # Draw marker based on style
                    if marker_style == "circle":
                        draw_circle_marker(draw, x, y, marker_size, color)
                    elif marker_style == "square":
                        draw_square_marker(draw, x, y, marker_size, color)
                    else:  # default to cross
                        draw_cross_marker(draw, x, y, marker_size, color)

                # Convert back to GIF frame format
                b = io.BytesIO()
                frame.save(b, format="GIF")
                frame = Image.open(b)
                frames.append(frame)

                # Move to next frame
                gif.seek(gif.tell() + 1)
                frame_count += 1

        except EOFError:
            # End of GIF frames
            pass

        # Save the new GIF with markers
        if frames:
            frames[0].save(
                out_gif,
                save_all=True,
                append_images=frames[1:],
                duration=gif.info.get("duration", 100),
                loop=gif.info.get("loop", 0),
                optimize=True,
            )

    except Exception as e:
        raise Exception(f"Error processing GIF: {str(e)}")


def draw_cross_marker(draw, x, y, size, color):
    """Draw a cross marker."""
    half_size = size // 2
    # Horizontal line
    draw.line([x - half_size, y, x + half_size, y], fill=color, width=3)
    # Vertical line
    draw.line([x, y - half_size, x, y + half_size], fill=color, width=3)
    # Add outline for better visibility
    draw.line([x - half_size, y, x + half_size, y], fill="white", width=1)
    draw.line([x, y - half_size, x, y + half_size], fill="white", width=1)


def draw_circle_marker(draw, x, y, size, color):
    """Draw a circle marker."""
    half_size = size // 2
    # Outer circle (outline)
    draw.ellipse(
        [x - half_size, y - half_size, x + half_size, y + half_size],
        outline="white",
        width=3,
    )
    # Inner circle (fill)
    draw.ellipse(
        [x - half_size + 2, y - half_size + 2, x + half_size - 2, y + half_size - 2],
        fill=color,
        outline=color,
    )


def draw_square_marker(draw, x, y, size, color):
    """Draw a square marker."""
    half_size = size // 2
    # Outer square (outline)
    draw.rectangle(
        [x - half_size, y - half_size, x + half_size, y + half_size],
        outline="white",
        width=3,
    )
    # Inner square (fill)
    draw.rectangle(
        [x - half_size + 2, y - half_size + 2, x + half_size - 2, y + half_size - 2],
        fill=color,
        outline=color,
    )


def get_pixel_coordinates_from_geo(lon, lat, roi_bounds, gif_width, gif_height):
    """Convert geographic coordinates to pixel coordinates.

    Args:
        lon (float): Longitude
        lat (float): Latitude
        roi_bounds (list): [min_lon, min_lat, max_lon, max_lat]
        gif_width (int): Width of GIF in pixels
        gif_height (int): Height of GIF in pixels

    Returns:
        tuple: (pixel_x, pixel_y)
    """
    min_lon, min_lat, max_lon, max_lat = roi_bounds

    # Linear transformation from geographic to pixel coordinates
    pixel_x = int(((lon - min_lon) / (max_lon - min_lon)) * gif_width)
    pixel_y = int(((max_lat - lat) / (max_lat - min_lat)) * gif_height)  # Flip Y axis

    # Ensure coordinates are within bounds
    pixel_x = max(0, min(gif_width - 1, pixel_x))
    pixel_y = max(0, min(gif_height - 1, pixel_y))

    return pixel_x, pixel_y


def combine_gif_with_chart(
    base_gif, chart_frames, chart_position, chart_size_ratio, spacer_width, fps, loop
):
    """Combine GIF with chart frames."""
    from PIL import Image, ImageDraw
    import tempfile

    # Open the base gif
    base_image = Image.open(base_gif)
    base_frames = []

    # Extract all frames from base gif
    try:
        while True:
            base_frames.append(base_image.copy())
            base_image.seek(base_image.tell() + 1)
    except EOFError:
        pass

    # Create combined frames
    combined_frames = []
    temp_dir = tempfile.mkdtemp()

    for i, base_frame in enumerate(base_frames):
        base_frame = base_frame.convert("RGB")

        # Get corresponding chart frame (cycle if needed)
        chart_idx = i % len(chart_frames) if chart_frames else 0

        if chart_frames:
            chart_frame = Image.open(chart_frames[chart_idx])
            chart_frame = chart_frame.convert("RGB")

            # Calculate dimensions
            base_width, base_height = base_frame.size
            chart_width, chart_height = chart_frame.size

            # Create combined image based on position
            if chart_position == "right":
                combined_width = base_width + spacer_width + chart_width
                combined_height = max(base_height, chart_height)
                combined_frame = Image.new(
                    "RGB", (combined_width, combined_height), "white"
                )
                combined_frame.paste(base_frame, (0, 0))
                combined_frame.paste(chart_frame, (base_width + spacer_width, 0))

            elif chart_position == "left":
                combined_width = chart_width + spacer_width + base_width
                combined_height = max(base_height, chart_height)
                combined_frame = Image.new(
                    "RGB", (combined_width, combined_height), "white"
                )
                combined_frame.paste(chart_frame, (0, 0))
                combined_frame.paste(base_frame, (chart_width + spacer_width, 0))

            elif chart_position == "bottom":
                combined_width = max(base_width, chart_width)
                combined_height = base_height + spacer_width + chart_height
                combined_frame = Image.new(
                    "RGB", (combined_width, combined_height), "white"
                )
                combined_frame.paste(base_frame, (0, 0))
                combined_frame.paste(chart_frame, (0, base_height + spacer_width))

            else:  # default to right
                combined_width = base_width + spacer_width + chart_width
                combined_height = max(base_height, chart_height)
                combined_frame = Image.new(
                    "RGB", (combined_width, combined_height), "white"
                )
                combined_frame.paste(base_frame, (0, 0))
                combined_frame.paste(chart_frame, (base_width + spacer_width, 0))

        else:
            combined_frame = base_frame

        combined_frames.append(combined_frame)

    # Save combined gif
    output_path = base_gif.replace(".gif", "_with_chart.gif")

    if combined_frames:
        combined_frames[0].save(
            output_path,
            save_all=True,
            append_images=combined_frames[1:],
            duration=int(1000 / fps),
            loop=loop,
            optimize=True,
        )

    # Clean up chart frames
    for frame_path in chart_frames:
        if os.path.exists(frame_path):
            os.remove(frame_path)

    return output_path


def landsat_timelapse_with_samples(
    roi,
    out_gif=None,
    start_year=1984,
    end_year=None,
    start_date="06-10",
    end_date="09-20",
    bands=["NIR", "Red", "Green"],
    frequency="year",
    reducer="median",
    date_format=None,
    palette=None,
    vis_params=None,
    dimensions=768,
    frames_per_second=10,
    crs="EPSG:3857",
    apply_fmask=True,
    overlay_data=None,
    overlay_color="black",
    overlay_width=1,
    overlay_opacity=1.0,
    title=None,
    title_xy=("2%", "90%"),
    add_text=True,
    text_xy=("2%", "2%"),
    text_sequence=None,
    font_type="arial.ttf",
    font_size=20,
    font_color="white",
    add_progress_bar=True,
    progress_bar_color="white",
    progress_bar_height=5,
    add_colorbar=False,
    colorbar_width=6.0,
    colorbar_height=0.4,
    colorbar_label=None,
    colorbar_label_size=12,
    colorbar_label_weight="normal",
    colorbar_tick_size=10,
    colorbar_bg_color=None,
    colorbar_orientation="horizontal",
    colorbar_dpi="figure",
    colorbar_xy=None,
    colorbar_size=(300, 300),
    loop=0,
    mp4=False,
    fading=False,
    step=1,
    sample_points=None,
    sample_point_crs="EPSG:4326",
    marker_colors=None,
    marker_size=50,
    marker_style="cross",
    show_sample_markers=True,
    chart_title="Landsat Time Series",
    chart_ylabel="Reflectance/Index Value",
    chart_position="right",
    chart_size_ratio=0.7,
    spacer_width=20,
    chart_xlabel_format="auto",
    chart_xlabel_interval="auto",
    sample_bands=None,
    chart_band_labels=None,
    indices=None,
    index_vis_params=None,
    **kwargs,
):
    """Create a Landsat timelapse with optional sample points and time series chart.

    Args:
        roi (ee.Geometry): The region to use to filter the collection of images.
        out_gif (str): The output gif file path. Defaults to None.
        start_year (int, optional): Starting year for the timelapse. Defaults to 1984.
        end_year (int, optional): Ending year for the timelapse. Defaults to the current year.
        start_date (str, optional): Starting date (month-day) each year. Defaults to '06-10'.
        end_date (str, optional): Ending date (month-day) each year. Defaults to '09-20'.
        bands (list, optional): Three bands for visualization. Defaults to ["NIR", "Red", "Green"].
        frequency (str, optional): The frequency of the timeseries. Defaults to 'year'.
        reducer (str, optional): The reducer to use. Defaults to 'median'.
        date_format (str, optional): Date format pattern. Defaults to None.
        palette (str, optional): Color palette for single-band visualization. Defaults to None.
        vis_params (dict, optional): Visualization parameters. Defaults to None.
        dimensions (int, optional): Maximum dimensions of the thumbnail. Defaults to 768.
        frames_per_second (int, optional): Animation speed. Defaults to 10.
        crs (str, optional): Coordinate reference system. Defaults to "EPSG:3857".
        apply_fmask (bool, optional): Whether to apply Fmask for cloud masking. Defaults to True.
        overlay_data (optional): Administrative boundary overlay. Defaults to None.
        overlay_color (str, optional): Color for overlay data. Defaults to 'black'.
        overlay_width (int, optional): Width of the overlay. Defaults to 1.
        overlay_opacity (float, optional): Opacity of the overlay. Defaults to 1.0.
        title (str, optional): The title of the timelapse. Defaults to None.
        title_xy (tuple, optional): Position of the title. Defaults to ("2%", "90%").
        add_text (bool, optional): Whether to add animated text. Defaults to True.
        text_xy (tuple, optional): Position of the text. Defaults to ("2%", "2%").
        text_sequence (optional): Text to be drawn. Defaults to None.
        font_type (str, optional): Font type. Defaults to "arial.ttf".
        font_size (int, optional): Font size. Defaults to 20.
        font_color (str, optional): Font color. Defaults to 'white'.
        add_progress_bar (bool, optional): Whether to add progress bar. Defaults to True.
        progress_bar_color (str, optional): Color for progress bar. Defaults to 'white'.
        progress_bar_height (int, optional): Height of progress bar. Defaults to 5.
        add_colorbar (bool, optional): Whether to add colorbar. Defaults to False.
        colorbar_width (float, optional): Width of colorbar. Defaults to 6.0.
        colorbar_height (float, optional): Height of colorbar. Defaults to 0.4.
        colorbar_label (str, optional): Label for colorbar. Defaults to None.
        colorbar_label_size (int, optional): Font size for colorbar label. Defaults to 12.
        colorbar_label_weight (str, optional): Font weight for colorbar label. Defaults to 'normal'.
        colorbar_tick_size (int, optional): Font size for colorbar ticks. Defaults to 10.
        colorbar_bg_color (str, optional): Background color for colorbar. Defaults to None.
        colorbar_orientation (str, optional): Orientation of colorbar. Defaults to 'horizontal'.
        colorbar_dpi (str, optional): DPI for colorbar. Defaults to 'figure'.
        colorbar_xy (tuple, optional): Position of colorbar. Defaults to None.
        colorbar_size (tuple, optional): Size of colorbar. Defaults to (300, 300).
        loop (int, optional): Number of animation loops. Defaults to 0.
        mp4 (bool, optional): Whether to create mp4 file. Defaults to False.
        fading (bool, optional): Whether to add fading effect. Defaults to False.
        step (int, optional): Step size for the timelapse. Defaults to 1.
        sample_points (list, optional): List of [lon, lat] coordinates for sampling (max 5 points). Defaults to None.
        sample_point_crs (str, optional): CRS for sample points. Defaults to "EPSG:4326".
        marker_colors (list, optional): Colors for markers. Defaults to None (uses default colors).
        marker_size (int, optional): Size of markers. Defaults to 50.
        marker_style (str, optional): Style of markers ('cross', 'circle', 'square'). Defaults to 'cross'.
        show_sample_markers (bool, optional): Whether to show markers on map. Defaults to True.
        chart_title (str, optional): Title for the time series chart. Defaults to "Landsat Time Series".
        chart_ylabel (str, optional): Y-axis label for chart. Defaults to "Reflectance/Index Value".
        chart_position (str, optional): Position of chart ('right', 'left', 'bottom'). Defaults to 'right'.
        chart_size_ratio (float, optional): Size ratio of chart to gif. Defaults to 0.7.
        spacer_width (int, optional): Width of spacer between gif and chart. Defaults to 20.
        chart_xlabel_format (str, optional): Format for x-axis labels ('auto', '%Y-%m', '%m-%d', '%Y-%m-%d'). Defaults to 'auto'.
        chart_xlabel_interval (str, optional): Interval for x-axis labels ('auto', 'day', 'week', 'month', 'year'). Defaults to 'auto'.
        sample_bands (list, optional): Which bands to sample for the chart. Defaults to first band only.
        chart_band_labels (dict, optional): Custom labels for bands in chart. Defaults to None.
        indices (list, optional): List of indices to calculate ['NDVI', 'EVI', 'NDWI', 'NDBI', 'MNDWI', 'NBR', 'SAVI', 'GNDVI', 'TCB', 'TCG', 'TCW']. Defaults to None.
        index_vis_params (dict, optional): Visualization parameters for indices. Defaults to None.
        **kwargs: Additional arguments for create_timeseries().

    Returns:
        str: File path to the output GIF with optional chart.
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    from datetime import datetime, date
    import tempfile
    import math

    # Handle indices parameter
    if indices is not None:
        if not isinstance(indices, list):
            indices = [indices]

        # Validate indices
        valid_indices = [
            "NDVI",
            "EVI",
            "NDWI",
            "MNDWI",
            "NDBI",
            "NBR",
            "SAVI",
            "GNDVI",
            "NDMI",
            "TCB",
            "TCG",
            "TCW",
            "MSAVI2",
            "VARI",
            "MCARI",
        ]
        for idx in indices:
            if idx not in valid_indices:
                raise ValueError(
                    f"Index '{idx}' not supported. Valid indices: {valid_indices}"
                )

        # If using indices, update defaults
        if sample_bands is None:
            sample_bands = indices[:1]  # Default to first index

        if chart_ylabel == "Reflectance/Index Value":
            if any(
                idx
                in [
                    "NDVI",
                    "EVI",
                    "NDWI",
                    "MNDWI",
                    "NDBI",
                    "NBR",
                    "SAVI",
                    "GNDVI",
                    "NDMI",
                    "MSAVI2",
                    "VARI",
                    "MCARI",
                ]
                for idx in indices
            ):
                chart_ylabel = "Index Value"
            elif any(idx in ["TCB", "TCG", "TCW"] for idx in indices):
                chart_ylabel = "Tasseled Cap Component"

        # Set up index visualization if not provided
        if index_vis_params is None:
            index_vis_params = get_default_landsat_index_vis_params()

        # For single index visualization, set up palette and vis_params
        if len(indices) == 1 and vis_params is None:
            index_name = indices[0]
            if palette is None and index_name in index_vis_params:
                palette = index_vis_params[index_name]["palette"]
                vis_params = {
                    "min": index_vis_params[index_name]["min"],
                    "max": index_vis_params[index_name]["max"],
                    "palette": palette,
                }

        # If visualizing an index, update bands for visualization
        if len(indices) == 1 and len(bands) == 3:
            # For single index, use that index for visualization
            bands = indices

    # Validate sample points
    if sample_points is not None:
        if not isinstance(sample_points, list):
            raise ValueError("sample_points must be a list of [lon, lat] coordinates")
        if len(sample_points) > 5:
            raise ValueError("Maximum 5 sample points are supported")
        if len(sample_points) == 0:
            sample_points = None

    # Set default marker colors if not provided
    if sample_points is not None and marker_colors is None:
        marker_colors = ["red", "blue", "green", "orange", "purple"][
            : len(sample_points)
        ]
    elif sample_points is not None and len(marker_colors) < len(sample_points):
        default_colors = ["red", "blue", "green", "orange", "purple"]
        marker_colors.extend(default_colors[len(marker_colors) : len(sample_points)])

    # Set default sample bands if not provided
    if sample_bands is None:
        sample_bands = [bands[0]] if bands else ["Red"]  # Default to first band or Red

    # Set default chart band labels
    if chart_band_labels is None:
        chart_band_labels = get_default_landsat_band_labels()
        # Add index labels
        index_labels = get_landsat_index_chart_labels()
        chart_band_labels.update(index_labels)

    # Adjust dimensions to avoid Earth Engine limits
    if isinstance(roi, ee.Geometry):
        roi_bounds = roi.bounds().getInfo()["coordinates"][0]
        min_lon = min([coord[0] for coord in roi_bounds])
        max_lon = max([coord[0] for coord in roi_bounds])
        min_lat = min([coord[1] for coord in roi_bounds])
        max_lat = max([coord[1] for coord in roi_bounds])

        # Calculate aspect ratio and adjust dimensions
        lon_range = max_lon - min_lon
        lat_range = max_lat - min_lat
        aspect_ratio = lon_range / lat_range if lat_range > 0 else 1

        max_pixels = 26214400  # Earth Engine limit

        if isinstance(dimensions, int):
            if aspect_ratio > 1:
                width = min(dimensions, int(math.sqrt(max_pixels * aspect_ratio)))
                height = int(width / aspect_ratio)
            else:
                height = min(dimensions, int(math.sqrt(max_pixels / aspect_ratio)))
                width = int(height * aspect_ratio)

            width = max(256, width)
            height = max(256, height)

            if width * height > max_pixels:
                scale_factor = math.sqrt(max_pixels / (width * height))
                width = int(width * scale_factor)
                height = int(height * scale_factor)

            adjusted_dimensions = f"{width}x{height}"
        else:
            adjusted_dimensions = dimensions

        print(f"Adjusted dimensions: {adjusted_dimensions}")
    else:
        adjusted_dimensions = dimensions

    # Create the base timelapse
    try:
        # If using indices, we need to create a custom timelapse that includes index calculation
        if indices is not None:
            base_gif = create_landsat_index_timelapse(
                roi=roi,
                out_gif=out_gif,
                start_year=start_year,
                end_year=end_year,
                start_date=start_date,
                end_date=end_date,
                bands=bands,
                indices=indices,
                vis_params=vis_params,
                dimensions=adjusted_dimensions,
                frames_per_second=frames_per_second,
                crs=crs,
                apply_fmask=apply_fmask,
                overlay_data=overlay_data,
                overlay_color=overlay_color,
                overlay_width=overlay_width,
                overlay_opacity=overlay_opacity,
                frequency=frequency,
                reducer=reducer,
                date_format=date_format,
                title=title,
                title_xy=title_xy,
                add_text=add_text,
                text_xy=text_xy,
                text_sequence=text_sequence,
                font_type=font_type,
                font_size=font_size,
                font_color=font_color,
                add_progress_bar=add_progress_bar,
                progress_bar_color=progress_bar_color,
                progress_bar_height=progress_bar_height,
                add_colorbar=add_colorbar,
                colorbar_width=colorbar_width,
                colorbar_height=colorbar_height,
                colorbar_label=colorbar_label,
                colorbar_label_size=colorbar_label_size,
                colorbar_label_weight=colorbar_label_weight,
                colorbar_tick_size=colorbar_tick_size,
                colorbar_bg_color=colorbar_bg_color,
                colorbar_orientation=colorbar_orientation,
                colorbar_dpi=colorbar_dpi,
                colorbar_xy=colorbar_xy,
                colorbar_size=colorbar_size,
                loop=loop,
                fading=fading,
                step=step,
                **kwargs,
            )
        else:
            # Use standard Landsat timelapse
            base_gif = landsat_timelapse(
                roi=roi,
                out_gif=out_gif,
                start_year=start_year,
                end_year=end_year,
                start_date=start_date,
                end_date=end_date,
                bands=bands,
                vis_params=vis_params,
                dimensions=adjusted_dimensions,
                frames_per_second=frames_per_second,
                crs=crs,
                apply_fmask=apply_fmask,
                overlay_data=overlay_data,
                overlay_color=overlay_color,
                overlay_width=overlay_width,
                overlay_opacity=overlay_opacity,
                frequency=frequency,
                date_format=date_format,
                title=title,
                title_xy=title_xy,
                add_text=add_text,
                text_xy=text_xy,
                text_sequence=text_sequence,
                font_type=font_type,
                font_size=font_size,
                font_color=font_color,
                add_progress_bar=add_progress_bar,
                progress_bar_color=progress_bar_color,
                progress_bar_height=progress_bar_height,
                loop=loop,
                mp4=False,
                fading=fading,
                step=step,
            )
    except Exception as e:
        print(f"Error creating base timelapse: {str(e)}")
        raise e

    # Check if base GIF was created successfully
    if not os.path.exists(base_gif):
        raise FileNotFoundError(f"Base timelapse GIF was not created: {base_gif}")

    # If no sample points, return the base gif (map only)
    if sample_points is None or len(sample_points) == 0:
        print("No sample points provided. Returning map-only timelapse.")
        if mp4:
            gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
        return base_gif

    # Get the Landsat time series for sampling
    if end_year is None:
        end_year = get_current_year()

    # Convert sample band names to Landsat band names if needed
    landsat_sample_bands = []
    for band in sample_bands:
        if band in chart_band_labels:
            # Try to map display names back to actual band names
            reverse_mapping = {v: k for k, v in chart_band_labels.items()}
            if band in reverse_mapping:
                landsat_sample_bands.append(reverse_mapping[band])
            else:
                landsat_sample_bands.append(band)
        elif band in [
            "NDVI",
            "EVI",
            "NDWI",
            "MNDWI",
            "NDBI",
            "NBR",
            "SAVI",
            "GNDVI",
            "NDMI",
            "TCB",
            "TCG",
            "TCW",
            "MSAVI2",
            "VARI",
            "MCARI",
        ]:
            landsat_sample_bands.append(band)  # Keep index names as-is
        else:
            landsat_sample_bands.append(band)

    # Create collection with error handling
    try:
        # Create time series - if using indices, we need to add index calculation
        if indices is not None:
            # Create base time series first
            base_ts_collection = landsat_timeseries(
                roi,
                start_year,
                end_year,
                start_date,
                end_date,
                apply_fmask,
                frequency,
                date_format,
                step,
            )

            # Add indices to each image
            ts_collection = base_ts_collection.map(calculate_landsat_indices)

            # Select only the bands we need for sampling
            ts_collection = ts_collection.select(landsat_sample_bands)
        else:
            # Standard time series without indices - use create_timeseries for consistency
            base_landsat_collection = landsat_timeseries(
                roi,
                start_year,
                end_year,
                start_date,
                end_date,
                apply_fmask,
                frequency,
                date_format,
                step,
            )

            # Select the sample bands
            ts_collection = base_landsat_collection.select(landsat_sample_bands)

        # Check if time series is empty
        ts_size = ts_collection.size().getInfo()
        if ts_size == 0:
            print("Warning: No time series data generated")
            if mp4:
                gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
            return base_gif

        print(f"Generated {ts_size} time series images")

    except Exception as e:
        print(f"Error creating time series: {str(e)}")
        # Return base gif without sampling
        if mp4:
            gif_to_mp4(base_gif, base_gif.replace(".gif", ".mp4"))
        return base_gif

    # Sample points from the time series
    sample_data = {}
    point_geometries = []

    if sample_points is not None and len(sample_points) > 0:
        try:
            for i, point in enumerate(sample_points):
                if sample_point_crs == "EPSG:4326":
                    geometry = ee.Geometry.Point([point[0], point[1]])
                else:
                    geometry = ee.Geometry.Point([point[0], point[1]], sample_point_crs)

                point_geometries.append(geometry)

                # Sample the time series at this point for each band
                for band_idx, band in enumerate(landsat_sample_bands):

                    def sample_point_band(image):
                        sampled = image.select(band).sample(geometry, 30)
                        return sampled.first().set(
                            {
                                "system:time_start": image.get("system:time_start"),
                                "system:date": image.get("system:date"),
                            }
                        )

                    sampled = ts_collection.map(sample_point_band)

                    # Get the time series data with error handling
                    try:
                        time_series = sampled.aggregate_array(
                            "system:time_start"
                        ).getInfo()
                        values = sampled.aggregate_array(band).getInfo()
                        dates = sampled.aggregate_array("system:date").getInfo()

                        # Filter out null values
                        valid_data = [
                            (t, v, d)
                            for t, v, d in zip(time_series, values, dates)
                            if v is not None
                        ]

                        if valid_data:
                            time_series, values, dates = zip(*valid_data)

                            # Convert timestamps to datetime objects
                            datetimes = [
                                datetime.fromtimestamp(ts / 1000) for ts in time_series
                            ]

                            # Create unique key for point and band combination
                            point_band_key = f"Point_{i+1}_{band}"
                            if len(landsat_sample_bands) == 1:
                                point_band_key = f"Point_{i+1}"

                            # Get display name for band
                            band_display = chart_band_labels.get(band, band)
                            if len(landsat_sample_bands) > 1:
                                label = f"Point {i+1} ({band_display})"
                            else:
                                label = f"Point {i+1}"

                            # Color assignment for multi-band sampling
                            if len(landsat_sample_bands) > 1:
                                base_color = (
                                    marker_colors[i]
                                    if i < len(marker_colors)
                                    else "red"
                                )
                                # Modify color for different bands
                                if band_idx == 0:
                                    color = base_color
                                elif band_idx == 1:
                                    color = (
                                        f"dark{base_color}"
                                        if base_color != "red"
                                        else "darkred"
                                    )
                                else:
                                    color = (
                                        f"light{base_color}"
                                        if base_color != "red"
                                        else "lightcoral"
                                    )
                            else:
                                color = (
                                    marker_colors[i]
                                    if i < len(marker_colors)
                                    else "red"
                                )

                            sample_data[point_band_key] = {
                                "dates": datetimes,
                                "values": list(values),
                                "date_strings": list(dates),
                                "color": color,
                                "geometry": geometry,
                                "label": label,
                                "band": band,
                                "point_idx": i,
                            }

                            print(f"Point {i+1} ({band}): {len(values)} valid samples")
                        else:
                            print(f"Warning: No valid data for point {i+1} ({band})")

                    except Exception as e:
                        print(f"Error sampling point {i+1} ({band}): {str(e)}")
                        continue

        except Exception as e:
            print(f"Error during point sampling: {str(e)}")
            sample_data = {}
    else:
        print("No sample points provided. Skipping sampling step.")

    # Add sample point markers to the base gif if requested
    if show_sample_markers and sample_points is not None and len(sample_points) > 0:
        try:
            # Get ROI bounds for coordinate conversion
            roi_bounds = roi.bounds().getInfo()["coordinates"][0]
            min_lon = min([coord[0] for coord in roi_bounds])
            max_lon = max([coord[0] for coord in roi_bounds])
            min_lat = min([coord[1] for coord in roi_bounds])
            max_lat = max([coord[1] for coord in roi_bounds])
            bounds = [min_lon, min_lat, max_lon, max_lat]

            # Add markers to the gif
            add_sample_markers_to_gif(
                base_gif,
                base_gif,
                sample_points,
                marker_colors,
                marker_size,
                marker_style,
                bounds,
                (
                    adjusted_dimensions
                    if "adjusted_dimensions" in locals()
                    else dimensions
                ),
            )
            print("Added sample markers to GIF")

        except Exception as e:
            print(f"Error adding markers to GIF: {str(e)}")

    # Create the time series chart if we have sample data
    if sample_data and len(sample_data) > 0:
        try:
            chart_frames = create_landsat_time_series_chart_frames(
                sample_data,
                chart_title,
                chart_ylabel,
                (
                    adjusted_dimensions
                    if "adjusted_dimensions" in locals()
                    else dimensions
                ),
                frames_per_second,
                chart_xlabel_format,
                chart_xlabel_interval,
            )

            # Combine gif and chart
            final_gif = combine_gif_with_chart(
                base_gif,
                chart_frames,
                chart_position,
                chart_size_ratio,
                spacer_width,
                frames_per_second,
                loop,
            )

            print("Created time series chart and combined with GIF")

        except Exception as e:
            print(f"Error creating chart: {str(e)}")
            final_gif = base_gif
    else:
        print("No sample data available. Returning map-only timelapse.")
        final_gif = base_gif

    # Handle MP4 conversion
    if mp4:
        gif_to_mp4(final_gif, final_gif.replace(".gif", ".mp4"))

    return final_gif


def calculate_landsat_indices(image):
    """Calculate common vegetation and spectral indices for Landsat images.

    Args:
        image (ee.Image): Landsat image with bands Blue, Green, Red, NIR, SWIR1, SWIR2

    Returns:
        ee.Image: Image with added index bands
    """
    # Normalized Difference Vegetation Index
    ndvi = image.normalizedDifference(["NIR", "Red"]).rename("NDVI")

    # Enhanced Vegetation Index
    evi = image.expression(
        "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))",
        {
            "NIR": image.select("NIR"),
            "RED": image.select("Red"),
            "BLUE": image.select("Blue"),
        },
    ).rename("EVI")

    # Normalized Difference Water Index
    ndwi = image.normalizedDifference(["Green", "NIR"]).rename("NDWI")

    # Modified Normalized Difference Water Index
    mndwi = image.normalizedDifference(["Green", "SWIR1"]).rename("MNDWI")

    # Normalized Difference Built-up Index
    ndbi = image.normalizedDifference(["SWIR1", "NIR"]).rename("NDBI")

    # Normalized Burn Ratio
    nbr = image.normalizedDifference(["NIR", "SWIR2"]).rename("NBR")

    # Soil Adjusted Vegetation Index
    savi = image.expression(
        "((NIR - RED) / (NIR + RED + 0.5)) * (1.5)",
        {"NIR": image.select("NIR"), "RED": image.select("Red")},
    ).rename("SAVI")

    # Green Normalized Difference Vegetation Index
    gndvi = image.normalizedDifference(["NIR", "Green"]).rename("GNDVI")

    # Normalized Difference Moisture Index
    ndmi = image.normalizedDifference(["NIR", "SWIR1"]).rename("NDMI")

    # Modified Soil Adjusted Vegetation Index 2
    msavi2 = image.expression(
        "(2 * NIR + 1 - sqrt(pow((2 * NIR + 1), 2) - 8 * (NIR - RED))) / 2",
        {"NIR": image.select("NIR"), "RED": image.select("Red")},
    ).rename("MSAVI2")

    # Visible Atmospherically Resistant Index
    vari = image.expression(
        "(GREEN - RED) / (GREEN + RED - BLUE)",
        {
            "GREEN": image.select("Green"),
            "RED": image.select("Red"),
            "BLUE": image.select("Blue"),
        },
    ).rename("VARI")

    # Modified Chlorophyll Absorption Ratio Index
    mcari = image.expression(
        "((RE - RED) - 0.2 * (RE - GREEN)) * (RE / RED)",
        {
            "RE": image.select("NIR"),  # Using NIR as proxy for Red Edge
            "RED": image.select("Red"),
            "GREEN": image.select("Green"),
        },
    ).rename("MCARI")

    # Tasseled Cap Transformation coefficients for Landsat 8 OLI
    # These coefficients are for surface reflectance data
    tcb = image.expression(
        "0.3037*BLUE + 0.2793*GREEN + 0.4743*RED + 0.5585*NIR + 0.5082*SWIR1 + 0.1863*SWIR2",
        {
            "BLUE": image.select("Blue"),
            "GREEN": image.select("Green"),
            "RED": image.select("Red"),
            "NIR": image.select("NIR"),
            "SWIR1": image.select("SWIR1"),
            "SWIR2": image.select("SWIR2"),
        },
    ).rename("TCB")

    tcg = image.expression(
        "-0.2848*BLUE - 0.2435*GREEN - 0.5436*RED + 0.7243*NIR + 0.0840*SWIR1 - 0.1800*SWIR2",
        {
            "BLUE": image.select("Blue"),
            "GREEN": image.select("Green"),
            "RED": image.select("Red"),
            "NIR": image.select("NIR"),
            "SWIR1": image.select("SWIR1"),
            "SWIR2": image.select("SWIR2"),
        },
    ).rename("TCG")

    tcw = image.expression(
        "0.1509*BLUE + 0.1973*GREEN + 0.3279*RED + 0.3406*NIR - 0.7112*SWIR1 - 0.4572*SWIR2",
        {
            "BLUE": image.select("Blue"),
            "GREEN": image.select("Green"),
            "RED": image.select("Red"),
            "NIR": image.select("NIR"),
            "SWIR1": image.select("SWIR1"),
            "SWIR2": image.select("SWIR2"),
        },
    ).rename("TCW")

    return image.addBands(
        [
            ndvi,
            evi,
            ndwi,
            mndwi,
            ndbi,
            nbr,
            savi,
            gndvi,
            ndmi,
            msavi2,
            vari,
            mcari,
            tcb,
            tcg,
            tcw,
        ]
    )


def get_default_landsat_index_vis_params():
    """Get default visualization parameters for different Landsat indices."""
    return {
        "NDVI": {
            "min": -0.1,
            "max": 1,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "EVI": {
            "min": -0.2,
            "max": 0.8,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "NDWI": {
            "min": -0.3,
            "max": 0.8,
            "palette": ["#8b4513", "#daa520", "#ffffbf", "#87ceeb", "#0000ff"],
        },
        "MNDWI": {
            "min": -0.3,
            "max": 0.8,
            "palette": ["#8b4513", "#daa520", "#ffffbf", "#87ceeb", "#0000ff"],
        },
        "NDBI": {
            "min": -0.5,
            "max": 0.5,
            "palette": ["#0000ff", "#87ceeb", "#ffffbf", "#daa520", "#8b4513"],
        },
        "NBR": {
            "min": -0.5,
            "max": 0.8,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "SAVI": {
            "min": -0.2,
            "max": 0.8,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "GNDVI": {
            "min": -0.2,
            "max": 0.8,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "NDMI": {
            "min": -0.2,
            "max": 0.6,
            "palette": ["#8b4513", "#daa520", "#ffffbf", "#87ceeb", "#0000ff"],
        },
        "MSAVI2": {
            "min": -0.2,
            "max": 0.8,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "VARI": {
            "min": -0.2,
            "max": 0.6,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "MCARI": {
            "min": 0,
            "max": 2,
            "palette": ["#d7191c", "#fdae61", "#ffffbf", "#abd9e9", "#2c7bb6"],
        },
        "TCB": {
            "min": 0,
            "max": 0.4,
            "palette": ["#000000", "#404040", "#808080", "#c0c0c0", "#ffffff"],
        },
        "TCG": {
            "min": -0.1,
            "max": 0.1,
            "palette": ["#8b4513", "#daa520", "#ffffbf", "#90ee90", "#006400"],
        },
        "TCW": {
            "min": -0.2,
            "max": 0.1,
            "palette": ["#8b4513", "#daa520", "#ffffbf", "#87ceeb", "#0000ff"],
        },
    }


def get_default_landsat_band_labels():
    """Get default chart labels for Landsat bands."""
    return {
        "Blue": "Blue",
        "Green": "Green",
        "Red": "Red",
        "NIR": "NIR",
        "SWIR1": "SWIR1",
        "SWIR2": "SWIR2",
    }


def get_landsat_index_chart_labels():
    """Get chart labels for different Landsat indices."""
    return {
        "NDVI": "NDVI",
        "EVI": "EVI",
        "NDWI": "NDWI",
        "MNDWI": "MNDWI",
        "NDBI": "NDBI",
        "NBR": "NBR",
        "SAVI": "SAVI",
        "GNDVI": "GNDVI",
        "NDMI": "NDMI",
        "MSAVI2": "MSAVI2",
        "VARI": "VARI",
        "MCARI": "MCARI",
        "TCB": "Tasseled Cap Brightness",
        "TCG": "Tasseled Cap Greenness",
        "TCW": "Tasseled Cap Wetness",
    }


def create_landsat_index_timelapse(
    roi,
    out_gif,
    start_year,
    end_year,
    start_date,
    end_date,
    bands,
    indices,
    vis_params,
    dimensions,
    frames_per_second,
    crs,
    apply_fmask,
    overlay_data,
    overlay_color,
    overlay_width,
    overlay_opacity,
    frequency,
    reducer,
    date_format,
    title,
    title_xy,
    add_text,
    text_xy,
    text_sequence,
    font_type,
    font_size,
    font_color,
    add_progress_bar,
    progress_bar_color,
    progress_bar_height,
    add_colorbar,
    colorbar_width,
    colorbar_height,
    colorbar_label,
    colorbar_label_size,
    colorbar_label_weight,
    colorbar_tick_size,
    colorbar_bg_color,
    colorbar_orientation,
    colorbar_dpi,
    colorbar_xy,
    colorbar_size,
    loop,
    fading,
    step,
    **kwargs,
):
    """Create a Landsat timelapse with indices."""
    if end_year is None:
        end_year = get_current_year()

    # Create time series with indices
    base_ts_collection = landsat_timeseries(
        roi,
        start_year,
        end_year,
        start_date,
        end_date,
        apply_fmask,
        frequency,
        date_format,
        step,
    )

    # Add indices to each image
    ts_collection = base_ts_collection.map(calculate_landsat_indices)

    # Use create_timelapse with the index collection
    start = f"{start_year}-{start_date}"
    end = f"{end_year}-{end_date}"

    return create_timelapse(
        ts_collection,
        start,
        end,
        roi,
        bands,
        frequency,
        reducer,
        date_format,
        out_gif,
        None,
        vis_params,
        dimensions,
        frames_per_second,
        crs,
        overlay_data,
        overlay_color,
        overlay_width,
        overlay_opacity,
        title,
        title_xy,
        add_text,
        text_xy,
        text_sequence,
        font_type,
        font_size,
        font_color,
        add_progress_bar,
        progress_bar_color,
        progress_bar_height,
        add_colorbar,
        colorbar_width,
        colorbar_height,
        colorbar_label,
        colorbar_label_size,
        colorbar_label_weight,
        colorbar_tick_size,
        colorbar_bg_color,
        colorbar_orientation,
        colorbar_dpi,
        colorbar_xy,
        colorbar_size,
        loop,
        False,
        fading,
        1,
        1,
    )


def create_landsat_time_series_chart_frames(
    sample_data,
    chart_title,
    chart_ylabel,
    dimensions,
    fps,
    xlabel_format="auto",
    xlabel_interval="auto",
):
    """Create frames for the Landsat time series chart with current time indicator.

    Args:
        sample_data (dict): Dictionary containing sample data for each point/band combination
        chart_title (str): Title for the chart
        chart_ylabel (str): Y-axis label
        dimensions (int/str): Dimensions for the chart
        fps (int): Frames per second
        xlabel_format (str): Format for x-axis labels
        xlabel_interval (str): Interval for x-axis labels

    Returns:
        list: List of paths to chart frame images
    """
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    from datetime import datetime
    import tempfile

    if not sample_data:
        return []

    # Get all unique dates across all points/bands
    all_dates = set()
    for point_data in sample_data.values():
        all_dates.update(point_data["dates"])

    if not all_dates:
        return []

    sorted_dates = sorted(list(all_dates))

    # Create chart frames
    chart_frames = []
    temp_dir = tempfile.mkdtemp()

    # Calculate chart dimensions
    if isinstance(dimensions, str) and "x" in dimensions:
        width, height = map(int, dimensions.split("x"))
    else:
        width = height = int(dimensions) if isinstance(dimensions, int) else 768

    chart_width = int(width * 0.8)  # 80% of gif width
    chart_height = height

    try:
        for frame_idx, current_date in enumerate(sorted_dates):
            fig, ax = plt.subplots(
                figsize=(chart_width / 100, chart_height / 100), dpi=100
            )

            # Plot all time series
            for point_key, point_data in sample_data.items():
                if point_data["dates"] and point_data["values"]:
                    # Use custom label if available, otherwise use point_key
                    label = point_data.get("label", point_key)

                    ax.plot(
                        point_data["dates"],
                        point_data["values"],
                        color=point_data["color"],
                        label=label,
                        linewidth=2,
                        marker="o",
                        markersize=4,
                    )

            # Add vertical line for current time
            ax.axvline(
                x=current_date, color="red", linestyle="--", linewidth=2, alpha=0.8
            )

            # Formatting
            ax.set_xlabel("Date", fontsize=10)
            ax.set_ylabel(chart_ylabel, fontsize=10)
            ax.set_title(chart_title, fontsize=12)
            ax.legend(fontsize=8, loc="upper left")
            ax.grid(True, alpha=0.3)

            # Format x-axis based on parameters or auto-detect
            date_range = (max(sorted_dates) - min(sorted_dates)).days

            if xlabel_format == "auto" or xlabel_interval == "auto":
                # Auto-detect based on data characteristics
                # Landsat typically has longer time series (annual data)
                if (
                    date_range <= 365
                ):  # Less than 1 year - likely monthly/quarterly data
                    format_str = "%Y-%m"
                    locator = mdates.MonthLocator(
                        interval=max(1, len(sorted_dates) // 8)
                    )
                elif date_range <= 1825:  # Less than 5 years - yearly data
                    format_str = "%Y"
                    locator = mdates.YearLocator()
                else:  # Long time series - multi-year intervals
                    format_str = "%Y"
                    year_interval = max(1, len(sorted_dates) // 15)
                    locator = mdates.YearLocator(interval=year_interval)
            else:
                # Use manual settings
                format_str = xlabel_format if xlabel_format != "auto" else "%Y"

                if xlabel_interval == "day":
                    locator = mdates.DayLocator(
                        interval=max(1, len(sorted_dates) // 15)
                    )
                elif xlabel_interval == "week":
                    locator = mdates.WeekdayLocator(
                        interval=max(1, len(sorted_dates) // 10)
                    )
                elif xlabel_interval == "month":
                    locator = mdates.MonthLocator(
                        interval=max(1, len(sorted_dates) // 8)
                    )
                elif xlabel_interval == "year":
                    locator = mdates.YearLocator()
                else:
                    locator = mdates.YearLocator()

            ax.xaxis.set_major_formatter(mdates.DateFormatter(format_str))
            ax.xaxis.set_major_locator(locator)

            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)

            # Set consistent y-axis limits
            all_values = []
            for point_data in sample_data.values():
                all_values.extend([v for v in point_data["values"] if v is not None])

            if all_values:
                y_min, y_max = min(all_values), max(all_values)
                y_range = y_max - y_min
                if y_range > 0:
                    ax.set_ylim(y_min - y_range * 0.1, y_max + y_range * 0.1)
                else:
                    ax.set_ylim(y_min - 0.01, y_max + 0.01)

            plt.tight_layout()

            # Save frame
            frame_path = os.path.join(temp_dir, f"chart_frame_{frame_idx:04d}.png")
            plt.savefig(frame_path, dpi=100, bbox_inches="tight", facecolor="white")
            plt.close()

            chart_frames.append(frame_path)

    except Exception as e:
        print(f"Error creating chart frames: {str(e)}")
        # Clean up any created frames
        for frame_path in chart_frames:
            if os.path.exists(frame_path):
                os.remove(frame_path)
        return []

    return chart_frames
