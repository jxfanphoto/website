#!/usr/bin/env python3
"""Build sRGB web images without modifying source artwork.

Requires Pillow with WebP and LittleCMS support. Re-run after replacing source
images, then update the image references if new artwork has been added.
"""

import hashlib
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageCms, ImageOps, ImageSequence


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "web"
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
PROFILE = SRGB.tobytes()


def color_convert(image, profile):
    """Convert embedded profiles; treat untagged RGB images as sRGB."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = image.convert("RGB")
    if profile:
        source = ImageCms.ImageCmsProfile(io.BytesIO(profile))
        rgb = ImageCms.profileToProfile(rgb, source, SRGB, outputMode="RGB")
    if alpha.getextrema() != (255, 255):
        rgb.putalpha(alpha)
    return rgb


def build(source):
    path = ROOT / source
    folder = OUTPUT / path.parent.relative_to(ROOT)
    folder.mkdir(parents=True, exist_ok=True)
    outputs = []
    with Image.open(path) as image:
        icc = image.info.get("icc_profile")
        xmp = image.info.get("xmp") or image.info.get("XML:com.adobe.xmp")
        if isinstance(xmp, str):
            xmp = xmp.encode("utf-8")
        metadata = {"icc_profile": PROFILE}
        if xmp:
            metadata["xmp"] = xmp
        # Keep attribution in EXIF as well as the complete existing XMP packet.
        exif = Image.Exif()
        original_exif = image.getexif()
        for tag in (315, 33432):  # Artist, Copyright
            if tag in original_exif:
                exif[tag] = original_exif[tag]
        if exif:
            metadata["exif"] = exif.tobytes()

        if getattr(image, "is_animated", False):
            frames, durations = [], []
            loop = image.info.get("loop", 1)
            for frame in ImageSequence.Iterator(image):
                durations.append(frame.info.get("duration", 100))
                frames.append(color_convert(frame, icc))
            target = folder / (path.stem + ".webp")
            frames[0].save(target, "WEBP", save_all=True,
                           append_images=frames[1:], duration=durations,
                           loop=loop, quality=78, method=4, **metadata)
            outputs.append({"src": target.relative_to(ROOT).as_posix(),
                            "width": image.width, "height": image.height,
                            "bytes": target.stat().st_size})
        else:
            converted = color_convert(ImageOps.exif_transpose(image), icc)
            longest = max(converted.size)
            if source.startswith("Logo/"):
                limits = [min(longest, 336)]
            elif source.startswith("Quadrangular/"):
                limits = [longest]
            else:
                limits = sorted({min(longest, limit) for limit in (640, 1280, 2400)})
            for limit in limits:
                resized = converted.copy()
                resized.thumbnail((limit, limit), Image.Resampling.LANCZOS)
                target = folder / f"{path.stem}-{limit}.webp"
                resized.save(target, "WEBP", quality=86, method=6,
                             lossless=source.startswith(("Logo/", "Quadrangular/")),
                             **metadata)
                outputs.append({"src": target.relative_to(ROOT).as_posix(),
                                "width": resized.width, "height": resized.height,
                                "bytes": target.stat().st_size})
    return {"original_bytes": path.stat().st_size,
            "original_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "variants": outputs}


def main():
    html = (ROOT / "index.html").read_text()
    # The manifest also keeps inputs discoverable after HTML points to web assets.
    manifest_path = OUTPUT / "manifest.json"
    existing = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    sources = set(existing)
    sources.update(re.findall(r'(?:src=|src: )?[\'\"]((?:Photoes|Exiperiments|Logo|Video)/[^\'\"]+\.(?:png|jpg|gif))[\'\"]', html))
    sources.update(f"Quadrangular/page_{number}_clean.png" for number in range(1, 13))
    manifest = {}
    for source in sorted(sources):
        manifest[source] = build(source)
        data = manifest[source]
        print(f"{source}: {data['original_bytes']:,} -> "
              f"{sum(v['bytes'] for v in data['variants']):,} bytes", flush=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Built {len(manifest)} source images.", flush=True)


if __name__ == "__main__":
    main()
