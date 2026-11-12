import os
import urllib.request
import yaml

# Anchor all paths to the directory this script lives in
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIBS_DIR = os.path.join(BASE_DIR, "libs")
FONTS_DIR = os.path.join(LIBS_DIR, "fonts")
CONFIG_FILE = os.path.join(BASE_DIR, "dependencies.yaml")


def check_and_install_dependencies():
    if not os.path.exists(CONFIG_FILE):
        print(f"Warning: {CONFIG_FILE} not found. Skipping automated dependency check.")
        return

    if not os.path.exists(LIBS_DIR):
        os.makedirs(LIBS_DIR)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 1. Download root libraries (CSS/JS)
        for dep in config.get("dependencies", []):
            name = dep.get("name")
            url = dep.get("url")
            file_path = os.path.join(LIBS_DIR, name)

            if not os.path.exists(file_path):
                print(f"Installing missing dependency: {name}...")
                try:
                    urllib.request.urlretrieve(url, file_path)
                    print(f"Successfully downloaded {name}")
                except Exception as e:
                    print(f"Error downloading {name}: {e}")

        # 2. Download KaTeX fonts into libs/fonts/
        fonts_list = config.get("fonts", [])
        if fonts_list:
            if not os.path.exists(FONTS_DIR):
                os.makedirs(FONTS_DIR)

            for font in fonts_list:
                name = font.get("name")
                url = font.get("url")
                font_path = os.path.join(FONTS_DIR, name)

                if not os.path.exists(font_path):
                    print(f"Installing missing font: {name}...")
                    try:
                        urllib.request.urlretrieve(url, font_path)
                        print(f"Successfully downloaded font {name}")
                    except Exception as e:
                        print(f"Error downloading font {name}: {e}")

    except Exception as e:
        print(f"Error parsing {CONFIG_FILE}: {e}")