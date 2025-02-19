import logging

from esphome import core
from esphome.components import display, font
import esphome.components.image as espImage
from esphome.components.image import CONF_USE_TRANSPARENCY
import esphome.config_validation as cv
import esphome.codegen as cg
from esphome.const import CONF_FILE, CONF_ID, CONF_RAW_DATA_ID, CONF_RESIZE, CONF_TYPE
from esphome.core import CORE, HexInt

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["display"]
MULTI_CONF = True

Animation_ = display.display_ns.class_("Animation", espImage.Image_)


def validate_cross_dependencies(config):
    """
    Validate fields whose possible values depend on other fields.
    For example, validate that explicitly transparent image types
    have "use_transparency" set to True.
    Also set the default value for those kind of dependent fields.
    """
    image_type = config[CONF_TYPE]
    is_transparent_type = image_type in ["TRANSPARENT_BINARY", "RGBA"]
    # If the use_transparency option was not specified, set the default depending on the image type
    if CONF_USE_TRANSPARENCY not in config:
        config[CONF_USE_TRANSPARENCY] = is_transparent_type

    if is_transparent_type and not config[CONF_USE_TRANSPARENCY]:
        raise cv.Invalid(f"Image type {image_type} must always be transparent.")

    return config


ANIMATION_SCHEMA = cv.Schema(
    cv.All(
        {
            cv.Required(CONF_ID): cv.declare_id(Animation_),
            cv.Required(CONF_FILE): cv.file_,
            cv.Optional(CONF_RESIZE): cv.dimensions,
            cv.Optional(CONF_TYPE, default="BINARY"): cv.enum(
                espImage.IMAGE_TYPE, upper=True
            ),
            # Not setting default here on purpose; the default depends on the image type,
            # and thus will be set in the "validate_cross_dependencies" validator.
            cv.Optional(CONF_USE_TRANSPARENCY): cv.boolean,
            cv.GenerateID(CONF_RAW_DATA_ID): cv.declare_id(cg.uint8),
        },
        validate_cross_dependencies,
    )
)

CONFIG_SCHEMA = cv.All(font.validate_pillow_installed, ANIMATION_SCHEMA)

CODEOWNERS = ["@syndlex"]


async def to_code(config):
    from PIL import Image

    path = CORE.relative_config_path(config[CONF_FILE])
    try:
        image = Image.open(path)
    except Exception as e:
        raise core.EsphomeError(f"Could not load image file {path}: {e}")

    width, height = image.size
    frames = image.n_frames
    if CONF_RESIZE in config:
        new_width_max, new_height_max = config[CONF_RESIZE]
        ratio = min(new_width_max / width, new_height_max / height)
        width, height = int(width * ratio), int(height * ratio)
    else:
        if width > 500 or height > 500:
            _LOGGER.warning(
                'The image "%s" you requested is very big. Please consider'
                " using the resize parameter.",
                path,
            )

    transparent = config[CONF_USE_TRANSPARENCY]

    if config[CONF_TYPE] == "GRAYSCALE":
        data = [0 for _ in range(height * width * frames)]
        pos = 0
        for frameIndex in range(frames):
            image.seek(frameIndex)
            frame = image.convert("LA", dither=Image.NONE)
            if CONF_RESIZE in config:
                frame = frame.resize([width, height])
            pixels = list(frame.getdata())
            if len(pixels) != height * width:
                raise core.EsphomeError(
                    f"Unexpected number of pixels in {path} frame {frameIndex}: ({len(pixels)} != {height*width})"
                )
            for pix, a in pixels:
                if transparent:
                    if pix == 1:
                        pix = 0
                    if a < 0x80:
                        pix = 1

                data[pos] = pix
                pos += 1

    elif config[CONF_TYPE] == "RGBA":
        data = [0 for _ in range(height * width * 4 * frames)]
        pos = 0
        for frameIndex in range(frames):
            image.seek(frameIndex)
            frame = image.convert("RGBA")
            if CONF_RESIZE in config:
                frame = frame.resize([width, height])
            pixels = list(frame.getdata())
            if len(pixels) != height * width:
                raise core.EsphomeError(
                    f"Unexpected number of pixels in {path} frame {frameIndex}: ({len(pixels)} != {height*width})"
                )
            for pix in pixels:
                data[pos] = pix[0]
                pos += 1
                data[pos] = pix[1]
                pos += 1
                data[pos] = pix[2]
                pos += 1
                data[pos] = pix[3]
                pos += 1

    elif config[CONF_TYPE] == "RGB24":
        data = [0 for _ in range(height * width * 3 * frames)]
        pos = 0
        for frameIndex in range(frames):
            image.seek(frameIndex)
            frame = image.convert("RGBA")
            if CONF_RESIZE in config:
                frame = frame.resize([width, height])
            pixels = list(frame.getdata())
            if len(pixels) != height * width:
                raise core.EsphomeError(
                    f"Unexpected number of pixels in {path} frame {frameIndex}: ({len(pixels)} != {height*width})"
                )
            for r, g, b, a in pixels:
                if transparent:
                    if r == 0 and g == 0 and b == 1:
                        b = 0
                    if a < 0x80:
                        r = 0
                        g = 0
                        b = 1

                data[pos] = r
                pos += 1
                data[pos] = g
                pos += 1
                data[pos] = b
                pos += 1

    elif config[CONF_TYPE] in ["RGB565", "TRANSPARENT_IMAGE"]:
        data = [0 for _ in range(height * width * 2 * frames)]
        pos = 0
        for frameIndex in range(frames):
            image.seek(frameIndex)
            frame = image.convert("RGBA")
            if CONF_RESIZE in config:
                frame = frame.resize([width, height])
            pixels = list(frame.getdata())
            if len(pixels) != height * width:
                raise core.EsphomeError(
                    f"Unexpected number of pixels in {path} frame {frameIndex}: ({len(pixels)} != {height*width})"
                )
            for r, g, b, a in pixels:
                R = r >> 3
                G = g >> 2
                B = b >> 3
                rgb = (R << 11) | (G << 5) | B

                if transparent:
                    if rgb == 0x0020:
                        rgb = 0
                    if a < 0x80:
                        rgb = 0x0020

                data[pos] = rgb >> 8
                pos += 1
                data[pos] = rgb & 0xFF
                pos += 1

    elif config[CONF_TYPE] in ["BINARY", "TRANSPARENT_BINARY"]:
        width8 = ((width + 7) // 8) * 8
        data = [0 for _ in range((height * width8 // 8) * frames)]
        for frameIndex in range(frames):
            image.seek(frameIndex)
            if transparent:
                alpha = image.split()[-1]
                has_alpha = alpha.getextrema()[0] < 0xFF
            frame = image.convert("1", dither=Image.NONE)
            if CONF_RESIZE in config:
                frame = frame.resize([width, height])
                if transparent:
                    alpha = alpha.resize([width, height])
            for x, y in [(i, j) for i in range(width) for j in range(height)]:
                if transparent and has_alpha:
                    if not alpha.getpixel((x, y)):
                        continue
                elif frame.getpixel((x, y)):
                    continue

                pos = x + y * width8 + (height * width8 * frameIndex)
                data[pos // 8] |= 0x80 >> (pos % 8)
    else:
        raise core.EsphomeError(
            f"Animation f{config[CONF_ID]} has not supported type {config[CONF_TYPE]}."
        )

    rhs = [HexInt(x) for x in data]
    prog_arr = cg.progmem_array(config[CONF_RAW_DATA_ID], rhs)
    var = cg.new_Pvariable(
        config[CONF_ID],
        prog_arr,
        width,
        height,
        frames,
        espImage.IMAGE_TYPE[config[CONF_TYPE]],
    )
    cg.add(var.set_transparency(transparent))
