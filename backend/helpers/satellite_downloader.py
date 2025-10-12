import uuid
import io
import math
import os
import re
import random
import sys
import time
from datetime import datetime

import argparse

import concurrent.futures
import threading

import requests

from PIL import Image, ImageOps, ImageChops
Image.MAX_IMAGE_PIXELS = None


TILE_SIZE = 256  # in pixels
EARTH_CIRCUMFERENCE = 40075.016686 * 1000  # in meters, at the equator

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36"

DEFAULT_VERSION = 908
DEFAULT_OBLIQUE_VERSION = 131  # both as of early October, 2021


class ViewDirection:
    """
    Keeps track of the selected view direction.
    """

    def __init__(self, direction):
        """
        The numbers (apart from '-1') are the view angles required for
        querying Google Maps - they're directly accessed during URL building for
        tile download.
        """

        self.angle = -1
        if direction == "downward":
            pass
        elif direction == "northward":
            self.angle = 0
        elif direction == "eastward":
            self.angle = 90
        elif direction == "southward":
            self.angle = 180
        elif direction == "westward":
            self.angle = 270
        else:
            raise ValueError(f"not a recognized view direction: {direction}")

        self.direction = direction

    def __repr__(self):
        return f"ViewDirection({self.direction})"

    def __str__(self):
        return self.direction

    def is_downward(self):
        return self.angle == -1

    def is_oblique(self):
        return not self.is_downward()

    def is_northward(self):
        return self.angle == 0

    def is_eastward(self):
        return self.angle == 90

    def is_southward(self):
        return self.angle == 180

    def is_westward(self):
        return self.angle == 270

class WebMercator:
    """Various functions related to the Web Mercator projection."""

    @staticmethod
    def project(geopoint, zoom):
        """
        An implementation of the Web Mercator projection (see
        https://en.wikipedia.org/wiki/Web_Mercator_projection#Formulas) that
        returns floats. That's required for cropping of stitched-together tiles
        such that they only show the configured area, hence no use of math.floor
        here.
        """

        factor = (1 / (2 * math.pi)) * 2 ** zoom
        x = factor * (math.radians(geopoint.lon) + math.pi)
        y = factor * (math.pi - math.log(math.tan((math.pi / 4) + (math.radians(geopoint.lat) / 2))))
        return (x, y)


class ObliqueWebMercator:
    """
    Various functions related to the Oblique Web Mercator projection as used for
    the 45 degree views available on Google Maps. The key (during projection) is
    dividing the y coordinate's distance from the equator by √2 to account for
    the foreshortening inherent in a 45 degree view - there's simply fewer
    vertical than horizontal pixels when viewing, say, a 1km square at a 45
    degree angle. Another variable that comes into play here (and not for the
    standard Web Mercator projection) is the direction your're looking (0
    degrees for northwards, i.e. the "camera" is south of what it's looking at,
    90 degrees for eastwards/rightwards, etc. clockwise) – here, the indexing
    of the tiles changes such that "up" remains towards decreasing y and "left"
    remains towards decreasing x.
    Complicated, I know, but at least *you* didn't need to reverse-engineer this
    from minified JavaScript code found in the shallows of the Internet Archive!
    """

    @staticmethod
    def project(geopoint, zoom, direction):
        """
        An implementation of the Oblique Web Mercator projection that returns
        floats. That's required for cropping of stitched-together tiles such
        that they only show the configured area, hence no use of `math.floor`
        here. Based on the Web Mercator projection, with corrections for
        obliqueness.
        """

        x0, y0 = WebMercator.project(geopoint, zoom)

        width_and_height_of_world_in_tiles = 2 ** zoom
        equator_offset_from_edges = width_and_height_of_world_in_tiles / 2

        # fiddle with tile coordinates depending on view direction
        x, y = x0, y0
        if direction.is_northward():
            pass
        elif direction.is_eastward():
            x = y0
            y = width_and_height_of_world_in_tiles - x0
        elif direction.is_southward():
            x = width_and_height_of_world_in_tiles - x0
            y = width_and_height_of_world_in_tiles - y0
        elif direction.is_westward():
            x = width_and_height_of_world_in_tiles - y0
            y = x0
        else:
            raise ValueError("direction must be one of 'northward', 'eastward', 'southward', or 'westward'")

        # translate such that the equator is at y=0, account for foreshortening,
        # then translate back
        y = ((y - equator_offset_from_edges) / math.sqrt(2)) + equator_offset_from_edges

        return (x, y)


class GeoPoint:
    """
    A latitude-longitude coordinate pair, in that order due to ISO 6709, see:
    https://stackoverflow.com/questions/7309121/preferred-order-of-writing-latitude-longitude-tuples
    """

    def __init__(self, lat, lon):
        assert -90 <= lat <= 90 and -180 <= lon <= 180

        self.lat = lat
        self.lon = lon

    def __repr__(self):
        return f"GeoPoint({self.lat}, {self.lon})"

    def to_maptile(self, version, zoom, direction):
        """
        Conversion of this geopoint to a tile through application of the Web
        Mercator projection and flooring to get integer tile corrdinates.
        """

        x, y = WebMercator.project(self, zoom)
        if direction.is_oblique():
            x, y = ObliqueWebMercator.project(self, zoom, direction)
        return MapTile(version, zoom, direction, math.floor(x), math.floor(y))

    def compute_zoom_level(self, max_meters_per_pixel):
        """
        Computes the outermost (i.e. lowest) zoom level that still fulfills the
        constraint. See:
        https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Resolution_and_Scale
        """

        meters_per_pixel_at_zoom_0 = ((EARTH_CIRCUMFERENCE / TILE_SIZE) * math.cos(math.radians(self.lat)))

        # 23 seems to be highest zoom level supported anywhere in the world, see
        # https://stackoverflow.com/a/32407072 (although 19 or 20 is the highest
        # in many places in practice)
        for zoom in reversed(range(0, 23+1)):
            meters_per_pixel = meters_per_pixel_at_zoom_0 / (2 ** zoom)

            # once meters_per_pixel eclipses the maximum, we know that the
            # previous zoom level was correct
            if meters_per_pixel > max_meters_per_pixel:
                return zoom + 1
        else:

            # if no match, the required zoom level would have been too high
            raise RuntimeError("your settings seem to require a zoom level higher than is commonly available")


class GeoRect:
    """
    A rectangle between two points. The first point must be the southwestern
    corner, the second point the northeastern corner:
       +---+ ne
       |   |
    sw +---+
    """

    def __init__(self, sw, ne):
        assert sw.lat <= ne.lat
        # not assert sw.lon < ne.lon since it may stretch across the date line

        self.sw = sw
        self.ne = ne

    def __repr__(self):
        return f"GeoRect({self.sw}, {self.ne})"

    @classmethod
    def around_geopoint(cls, geopoint, width, height):
        """
        Creates a rectangle with the given point at its center. Like the random
        point generator, this accounts for high-latitude longitudes being closer
        together than at the equator. See also:
        https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Resolution_and_Scale
        """

        assert width > 0 and height > 0

        meters_per_degree = (EARTH_CIRCUMFERENCE / 360)

        width_geo = width / (meters_per_degree * math.cos(math.radians(geopoint.lat)))
        height_geo = height / meters_per_degree

        southwest = GeoPoint(geopoint.lat - height_geo / 2, geopoint.lon - width_geo / 2)
        northeast = GeoPoint(geopoint.lat + height_geo / 2, geopoint.lon + width_geo / 2)

        return cls(southwest, northeast)


class MapTileStatus:
    """An enum type used to keep track of the current status of map tiles."""

    PENDING = 1
    DOWNLOADING = 2
    DOWNLOADED = 3
    ERROR = 4


class MapTile:
    """
    A map tile: coordinates and, if it's been downloaded yet, image, plus some
    housekeeping stuff.
    """

    def __init__(self, version, zoom, direction, x, y):
        self.version = version
        self.zoom = zoom
        self.direction = direction
        self.x = x
        self.y = y

        # initialize the other variables
        self.status = MapTileStatus.PENDING
        self.image = None

    def __repr__(self):
        return f"MapTile({self.version}, {self.zoom}, {self.direction}, {self.x}, {self.y})"

    def load(self):
        """
        Downloads the tile image if it hasn't been downloaded yet. Can be used
        for retrying on errors.
        """

        if self.status != MapTileStatus.DOWNLOADED:
            self.download()


    def download(self):
        """
        Downloads a tile image. Sets the status to ERROR if things don't work
        out for whatever reason.
        """

        self.status = MapTileStatus.DOWNLOADING

        try:
            url_template = "https://khms1.google.com/kh/v={version}?x={x}&y={y}&z={zoom}"
            if self.direction.is_oblique():
                url_template = "https://khms1.googleapis.com/kh?v={version}&deg={angle}&x={x}&y={y}&z={zoom}"
            url = url_template.format(version=self.version, angle=self.direction.angle, x=self.x, y=self.y, zoom=self.zoom)
            r = requests.get(url, headers={"User-Agent": USER_AGENT})
        except requests.exceptions.ConnectionError:
            self.status = MapTileStatus.ERROR
            return

        # error handling
        if r.status_code != 200:
            self.status = MapTileStatus.ERROR
            return

        # convert response into an image
        data = r.content
        self.image = Image.open(io.BytesIO(data))

        # sanity check
        assert self.image.mode == "RGB"
        assert self.image.size == (TILE_SIZE, TILE_SIZE)

        # done!
        self.status = MapTileStatus.DOWNLOADED


class ProgressIndicator:
    """
    Displays and updates a progress indicator during tile download. Designed
    to run in a separate thread, polling for status updates frequently.
    """

    def __init__(self, maptilegrid):
        self.maptilegrid = maptilegrid

    def update_tile(self, maptile):
        """
        Updates a single tile depending on its state: pending tiles are grayish,
        downloading tiles are yellow, successfully downloaded tiles are green,
        and tiles with errors are red. For each tile, two characters are printed
        – in most fonts, this is closer to a square than a single character.
        See https://stackoverflow.com/a/39452138 for color escapes.
        """

        def p(s): print(s + "\033[0m", end="")

        if maptile.status == MapTileStatus.PENDING:
            p("░░")
        elif maptile.status == MapTileStatus.DOWNLOADING:
            p("\033[33m" + "▒▒")
        elif maptile.status == MapTileStatus.DOWNLOADED:
            p("\033[32m" + "██")
        elif maptile.status == MapTileStatus.ERROR:
            p("\033[41m\033[37m" + "XX")

    def update_text(self):
        """
        Displays percentage and counts only.
        """

        downloaded = 0
        errors = 0
        for maptile in self.maptilegrid.flat():
            if maptile.status == MapTileStatus.DOWNLOADED:
                downloaded += 1
            elif maptile.status == MapTileStatus.ERROR:
                errors += 1

        total = self.maptilegrid.width * self.maptilegrid.height
        percent = int(10 * (100 * downloaded / total)) / 10

        details = f"{downloaded}/{total}"
        if errors:
            details += f", {errors} error"
            if errors > 1:
                details += "s"


        # need a line break after it so that the first line of the next
        # iteration of the progress indicator starts at col 0
        print(f"{percent}% ({details})")

    def update(self):
        """Updates the progress indicator."""

        for y in range(self.maptilegrid.height):
            for x in range(self.maptilegrid.width):
                maptile = self.maptilegrid.at(x, y)
                self.update_tile(maptile)
            print()  # line break

        self.update_text()

        # move cursor back up to the beginning of the progress indicator for
        # the next iteration, see
        # http://www.tldp.org/HOWTO/Bash-Prompt-HOWTO/x361.html
        print(f"\033[{self.maptilegrid.height + 1}A", end="")

    def loop(self):
        """Main loop."""

        while any([maptile.status is MapTileStatus.PENDING or
                   maptile.status is MapTileStatus.DOWNLOADING
                   for maptile in self.maptilegrid.flat()]):
            self.update()
            time.sleep(0.1)
        self.update()  # final update to show that we're all done

    def cleanup(self):
        """Moves the cursor back to the bottom after completion."""

        print(f"\033[{self.maptilegrid.height}B")


class MissingTilesError(Exception):
    """Exception raised when a MapTileGrid couldn't be completely downloaded."""

    def __init__(self, message, missing, total):
        self.message = message
        self.missing = missing
        self.total = total

    def __str__(self):
        return self.message


class MapTileGrid:
    """
    A grid of map tiles, kepts as a nested list such that indexing works via
    [x][y]. Manages the download and stitching of map tiles into a preliminary
    result image.
    """

    def __init__(self, maptiles, version):
        self.maptiles = maptiles
        self.version = version

        self.width = len(maptiles)
        self.height = len(maptiles[0])
        self.image = None

    def __repr__(self):
        return f"MapTileGrid({self.maptiles})"

    @classmethod
    def from_georect(cls, georect, zoom, direction, version):
        """Divides a GeoRect into a grid of map tiles."""

        bottomleft = georect.sw.to_maptile(version, zoom, direction)
        topright = georect.ne.to_maptile(version, zoom, direction)

        # this swapping business is really only required when the direction is
        # "eastward", "southward", or "westward" since in these cases, tile
        # coordinates are rotated with respect to the "downward" or "northward"
        # directions (where they match cardinal directions) – note that the
        # alternative to this sorting step would be four cases (similar to how
        # it's done in the `ObliqueWebMercator.project` function)
        if bottomleft.x > topright.x:
            bottomleft.x, topright.x = topright.x, bottomleft.x
        if bottomleft.y < topright.y:
            bottomleft.y, topright.y = topright.y, bottomleft.y

        maptiles = []
        for x in range(bottomleft.x, topright.x + 1):
            col = []

            # it's correct to have `topright` (i.e. "northeast" when direction
            # is "downward" or "northward") and `bottomleft` (i.e. similarly
            # "southwest") reversed here (with regard to the outer loop) since
            # the y axis of the tile coordinates points toward the south, while
            # the latitude axis points due north
            for y in range(topright.y, bottomleft.y + 1):
                maptile = MapTile(version, zoom, direction, x, y)
                col.append(maptile)
            maptiles.append(col)

        return cls(maptiles, version)

    def at(self, x, y):
        """Accessor with wraparound for negative values: x/y<0 => x/y+=w/h."""

        if x < 0:
            x += self.width
        if y < 0:
            y += self.height
        return self.maptiles[x][y]

    def flat(self):
        """Returns the grid as a flattened list."""

        return [maptile for col in self.maptiles for maptile in col]

    def download(self):
        """
        Downloads the constitudent tiles using a threadpool for performance
        while updating the progress indicator.
        """

        # set up progress indicator
        prog = ProgressIndicator(self)
        prog_thread = threading.Thread(target=prog.loop)
        prog_thread.start()

        # shuffle the download order of the tiles, this serves no actual purpose
        # but it makes the progress indicator look really cool!
        tiles = self.flat()
        random.shuffle(tiles)

        # download tiles using threadpool (2-10 times faster than
        # [maptile.load() for maptile in self.flat()]), see
        # https://docs.python.org/dev/library/concurrent.futures.html#threadpoolexecutor-example
        threads = max(self.width, self.height)
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            {executor.submit(maptile.load): maptile for maptile in tiles}

        # retry failed downloads if fewer than 20% of tiles are missing
        missing_tiles = [maptile for maptile in self.flat() if maptile.status == MapTileStatus.ERROR]
        if 0 < len(missing_tiles) < 0.2 * len(self.flat()):
            print("Retrying missing tiles...")
            for maptile in missing_tiles:
                maptile.load()

        # finish up progress indicator
        prog_thread.join()
        prog.cleanup()

        # check if we've got everything now
        missing_tiles = [maptile for maptile in self.flat() if maptile.status == MapTileStatus.ERROR]
        if missing_tiles:
            raise MissingTilesError(f"unable to download one or more map tiles", len(missing_tiles), len(self.flat()))

    def corners(self):
        """
        Returns a list of the four tiles in the corners of the grid. If the grid
        consists of only one or two tiles, they will occur multiple times.
        """

        return [self.at(x, y) for x in [0, -1] for y in [0, -1]]


    def corners_identical_to(self, other):
        """
        Checks whether the four corners of this grid are identical to the ones
        from another grid. The other grid MUST already be fully loaded (or, at
        least, its corners must be available).
        """

        self_corners = self.corners()
        other_corners = other.corners()
        assert all([maptile.status == MapTileStatus.DOWNLOADED for maptile in other_corners])

        # download self's corners
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            {executor.submit(maptile.load): maptile for maptile in self_corners}

        # retry
        missing_tiles = [maptile for maptile in self_corners if maptile.status == MapTileStatus.ERROR]
        for maptile in missing_tiles:
            maptile.load()
        missing_tiles = [maptile for maptile in self_corners if maptile.status == MapTileStatus.ERROR]
        if missing_tiles:
            raise MissingTilesError(f"unable to download one or more corner tiles", len(missing_tiles), len(self_corners))

        # super basic difference metric: just sum up the differences of each
        # channel for every pixel (for every corner) – you'd think this would be
        # slow, but it takes 0.2s on my early 2015 laptop for all four combined
        # (the connection setup latency during download is the limiting factor!)
        for self_corner, other_corner in zip(self_corners, other_corners):
            diff = ImageChops.difference(self_corner.image, other_corner.image)
            if any([True for channels in list(diff.getdata()) if channels != (0, 0, 0)]):
                return False

        return True

    def stitch(self):
        """
        Stitches the tiles comprising this grid together. Must not be called
        before all tiles have been loaded.
        """

        image = Image.new("RGB", (self.width * TILE_SIZE, self.height * TILE_SIZE))
        for x in range(0, self.width):
            for y in range(0, self.height):
                image.paste(self.maptiles[x][y].image, (x * TILE_SIZE, y * TILE_SIZE))
        self.image = image


class MapTileImage:
    """Image cropping, resizing and enhancement."""

    def __init__(self, image, version):
        self.image = image
        self.version = version

    def save(self, path, quality=90):
        self.image.save(path, quality=quality)

    def crop(self, zoom, direction, georect):
        """
        Crops the image such that it really only covers the area within the
        input `GeoRect`. This function must only be called once per image.
        """

        left, bottom = WebMercator.project(georect.sw, zoom)  # sw_x, sw_y
        right, top = WebMercator.project(georect.ne, zoom)  # ne_x, ne_y
        if direction.is_oblique():
            left, bottom = ObliqueWebMercator.project(georect.sw, zoom, direction)
            right, top = ObliqueWebMercator.project(georect.ne, zoom, direction)

        # swapping (and naming) analogous to how/why it's done in
        # `MapTileGrid.from_georect`
        if left > right:
            left, right = right, left
        if bottom < top:
            bottom, top = top, bottom

        # determine what we'll cut off
        left_crop = round(TILE_SIZE * (left % 1))
        bottom_crop = round(TILE_SIZE * (1 - bottom % 1))
        right_crop = round(TILE_SIZE * (1 - right % 1))
        top_crop = round(TILE_SIZE * (top % 1))

        crop = (left_crop, top_crop, right_crop, bottom_crop)

        # snip snap
        self.image = ImageOps.crop(self.image, crop)

    def scale(self, width, height):
        """
        Scales an image. This can distort the image if width and height don't
        match the original aspect ratio.
        """

        # Image.LANCZOS apparently provides the best quality, see
        # https://pillow.readthedocs.io/en/latest/handbook/concepts.html#concept-filters
        self.image = self.image.resize((round(width), round(height)), resample=Image.LANCZOS)

    def tobytes(self):
        # Convert image to bytes and encode as base64 for safe transmission
        import base64
        import io
        img_byte_arr = io.BytesIO()
        self.image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        return base64.b64encode(img_byte_arr).decode('utf-8')

class Printer:
    def __init__(self, verbose):
        self.verbose = verbose

    def head(self, message):
        print(f"\033[1m{message}\033[0m")

    def info(self, message):
        print(message)

    def debug(self, message):
        if self.verbose:
            print(f"\033[2m{message}\033[0m")

    def warn(self, message):
        print(f"\033[35m{message}\033[0m")

class SatelliteDownloader:

    def __init__(self):
        pass

    def download(self, latitude: float, longitude: float, zoom: int=1000):
        # Generate an image_id
        image_id = uuid.uuid4()

        # process options
        p = GeoPoint(latitude, longitude)
        direction = ViewDirection("downward")

        current_version = DEFAULT_VERSION
        if direction.is_oblique():
            current_version = DEFAULT_OBLIQUE_VERSION

        width = zoom
        height = zoom

        # if looking eastwards or westwards, the height of the *geographical* area
        # (where "height" = "latitude range" and "width" = "longitude range") must
        # be swapped to match the intended dimensions of the *imaged* area
        geowidth = width
        geoheight = height
        if direction.is_eastward() or direction.is_westward():
            geowidth, geoheight = geoheight, geowidth

        image_width = 2048
        image_height = 2048

        output_format = "jpegs" #jpegs,gifs,both

        quality = 90

        image_path_template = "data/{image_id}/googlemapsat88mph-{datetime}-{direction}-v{versions}-x{xmin}..{xmax}y{ymin}..{ymax}-z{zoom}-{latitude},{longitude}-{width}x{height}m"

        foreshortening_factor = 1
        if direction.is_oblique():
            foreshortening_factor = math.sqrt(2)

        max_meters_per_pixel = None
        framerate = 10


        # process max_meters_per_pixel option
        if image_width is None and image_height is None:
            if max_meters_per_pixel is None:
                raise ValueError("neither image height nor width given, so a maximum meters per pixel constraint needs to be specified")
        elif image_height is None:
            max_meters_per_pixel = (max_meters_per_pixel or 1) * (width / image_width)
        elif image_width is None:
            max_meters_per_pixel = (max_meters_per_pixel or 1) * (height / image_height) / foreshortening_factor
        else:
            # if both are set, effectively use whatever imposes a tighter constraint
            if width / image_width <= (height / image_height) / foreshortening_factor:
                max_meters_per_pixel = (max_meters_per_pixel or 1) * (width / image_width)
            else:
                max_meters_per_pixel = (max_meters_per_pixel or 1) * (height / image_height) / foreshortening_factor

        # process image width and height for scaling
        if image_width is not None or image_height is not None:
            if image_height is None:
                image_height = height * (image_width / width) / foreshortening_factor
            elif image_width is None:
                image_width = width * (image_height / height) * foreshortening_factor

        ############################################################################

        print("Determining current Google Maps version (we'll work our way backwards from there)...")
        try:
            google_maps_page = requests.get("https://maps.googleapis.com/maps/api/js", headers={"User-Agent": USER_AGENT}).content
            match = re.search(rb'null,\[\[\"https:\/\/khms0\.googleapis\.com\/kh\?v=([0-9]+)', google_maps_page)
            if direction.is_oblique():
                match = re.search(rb'\],\[\[\"https:\/\/khms0\.googleapis\.com\/kh\?v=([0-9]+)', google_maps_page)
            if match:
                current_version = int(match.group(1).decode("ascii"))
            else:
                print(f"Unable to extract current version, proceeding with outdated version {current_version} instead.")
        except requests.RequestException:
            print(f"Unable to load Google Maps, proceeding with outdated version {current_version} instead.")

        print("Computing required tile zoom level at specified point...")
        zoom = p.compute_zoom_level(max_meters_per_pixel)
        print(zoom)

        print("Generating rectangle with your selected width and height around point...")
        rect = GeoRect.around_geopoint(p, geowidth, geoheight)
        print(rect)

        ############################################################################

        print("Alrighty, prep work's done!")

        previous_grid = None
        downloaded_images = []
        skipped_versions = 0
        identical_versions = 0
        for version in range(current_version, -1, -1):
            try:
                print(f"Version {version}")

                print("Turning rectangle into a grid of map tiles at the required zoom level and for the current version...")
                grid = MapTileGrid.from_georect(rect, zoom, direction, version)
                print(grid)

                # if we're not on the first iteration, check if the imagery differs at the corners
                if version != current_version:
                    print("Downloading corner tiles and comparing with previously downloaded version...")
                    if grid.corners_identical_to(previous_grid):
                        identical_versions += 1
                        
                        if identical_versions >= 3:
                            print("Imagery seems identical, going to next version instead of downloading this one...")
                            continue
                    print("They're different! So:")

                previous_grid = grid

                print("Downloading tiles...")
                grid.download()

                print("Stitching tiles together into an image...")
                grid.stitch()
                image = MapTileImage(grid.image, version)

                print("Cropping image to match the chosen area width and height...")
                print((width, height))
                image.crop(zoom, direction, rect)

                if image_width is not None or image_height is not None:
                    print("Scaling image...")
                    print((image_width, image_height))
                    image.scale(image_width, image_height)

                if output_format != "gif":
                    print("Saving image to disk...")

                    # Create a directory for the image if it doesn't exist
                    os.makedirs(f"data/{image_id}", exist_ok=True)

                    image_path = (image_path_template + ".jpg").format(
                        image_id=image_id,
                        datetime=datetime.today().strftime("%Y-%m-%dT%H.%M.%S"),
                        direction="downward",
                        versions=version,
                        xmin=grid.at(0, 0).x,
                        xmax=grid.at(0, 0).x+grid.width,
                        ymin=grid.at(0, 0).y,
                        ymax=grid.at(0, 0).y+grid.height,
                        zoom=zoom,
                        latitude=p.lat,
                        longitude=p.lon,
                        width=width,
                        height=height
                    )
                    print(image_path)
                    image_quality = quality
                    image.save(image_path, image_quality)

                # keep track of downloaded images for gif writing
                downloaded_images.append(image)

                # reset skipped versions counter
                skipped_versions = 0
        
                # return downloaded_images

            except MissingTilesError as e:

                # provide a good error message if not even the ostensibly-current
                # version could be downloaded
                if version == current_version:
                    print(f"Couldn't download the current version, not to mention any previous ones – either your connection's wonky or imagery plain doesn't exist for the selected area at the computed zoom level.")
                    break

                # try skipping to an older version in case an intermediate one has been removed
                if skipped_versions < 3:
                    print(f"Couldn't download version {version}, skipping...")
                    skipped_versions += 1
                    continue

                # otherwise, exit with some semblance of grace
                print(f"It appears as though versions {version + skipped_versions} through {version} (and probably more) have been purged, or your internet connection has (at least partially) disappeared – either way, this seems to be the end of the line.")

                if output_format != "jpeg" or output_format != "jpegs":

                    # reverse downloaded images list to proceed from oldest to newest
                    downloaded_images.reverse()

                    # Create a directory for the image if it doesn't exist
                    os.makedirs(f"data/{image_id}", exist_ok=True)

                    print("Skipping GIF...")
                    # image_path = (image_path_template + ".gif").format(
                    #     image_id=image_id,
                    #     datetime=datetime.today().strftime("%Y-%m-%dT%H.%M.%S"),
                    #     direction="downward",
                    #     versions=",".join(map(lambda i: str(i.version), downloaded_images)),
                    #     xmin=grid.at(0, 0).x,
                    #     xmax=grid.at(0, 0).x+grid.width,
                    #     ymin=grid.at(0, 0).y,
                    #     ymax=grid.at(0, 0).y+grid.height,
                    #     zoom=zoom,
                    #     latitude=p.lat,
                    #     longitude=p.lon,
                    #     width=width,
                    #     height=height
                    # )
                    # downloaded_images[0].image.save(image_path, append_images=[i.image for i in downloaded_images[1:]], save_all=True, duration=1000/framerate, loop=0)
                    # print(image_path)

                print("All done! 🛰")

                # exit the loop (thereby terminate the program)
                return image_id, downloaded_images
