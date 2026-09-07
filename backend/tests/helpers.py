"""Test helper to load a Lambda handler module by its function directory name.

Each Lambda lives in src/<name>/app.py and they are all named ``app``. Loading
them by explicit file path (with a unique module name) avoids import collisions.
"""
import importlib.util
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_handler(function_name):
    path = os.path.join(BACKEND_DIR, "src", function_name, "app.py")
    spec = importlib.util.spec_from_file_location(f"handler_{function_name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
