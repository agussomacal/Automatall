import os
import urllib.request
import yaml

# Anchor all paths to the directory this script lives in, so the app works
# no matter what the current working directory is when it is launched.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LIBS_DIR = os.path.join(BASE_DIR, "libs")
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
    except Exception as e:
        print(f"Error parsing {CONFIG_FILE}: {e}")
