# Personal website

The site loads sRGB WebP images from `assets/web/`. Original artwork remains in
`Photoes/`, `Exiperiments/`, `Quadrangular/`, and `Video/`.

To regenerate the web images with Pillow (WebP and LittleCMS support required):

```sh
python3 scripts/optimize_images.py
```

The script preserves existing XMP copyright metadata, converts embedded color
profiles to sRGB, and treats untagged RGB images as sRGB. Photos have variants
up to 640, 1280, and 2400 pixels on the long edge; logos and book pages use
lossless WebP. Animated previews retain their playback timing and loop settings.

`assets/web/manifest.json` records source checksums and generated dimensions and
sizes. After adding images or changing their dimensions, use that manifest to
update the image references in `index.html`. Hidden pages use `data-src` and
`data-srcset`; artwork viewers use `data-full-src` for the largest version.
