"""
This was an attempt to make cute and clever code to dynamically discover and
import all applet modules of a certain type for aggregation purposes (e.g. the
authoring/models.py file importing from all applet models.py files). This code
actually does work, but I only realized after buildling it that it breaks
editor introspection/autocomplete, which makes the cost far too high for this
convenience.
"""

import functools
import importlib
import inspect
import pathlib


def auto_import(module_name):
    caller_frame_info = inspect.stack()[1]
    caller_module = inspect.getmodule(caller_frame_info[0])
    caller_module_name = caller_module.__name__

    # converts openedx_learning.authoring.models -> openedx_learning.authoring
    import_base = ".".join(caller_module_name.split(".")[:-1])

    caller_filepath = caller_frame_info.filename
    caller_dir = pathlib.Path(caller_filepath).resolve().parent
    applets_dir = caller_dir / "applets"
    module_paths = applets_dir.rglob(f"{module_name}.py")
    relative_paths = [
        module_path.relative_to(caller_dir) for module_path in module_paths
    ]
    all_modules_dict = {}
    for relative_path in sorted(relative_paths):
        module_import_name = f"{import_base}." + ".".join(relative_path.parts)[:-3]
        module = importlib.import_module(module_import_name)
        module_dict = vars(module)
        if '__all__' in module_dict:
            module_dict_to_add = {
                key: module_dict[key]
                for key in module_dict['__all__']
            }
        else:
            module_dict_to_add = {
                key: val
                for (key, val) in module_dict.items()
                if not key.startswith('_')
            }
        all_modules_dict.update(module_dict_to_add)

    return all_modules_dict


auto_import_models = functools.partial(auto_import, "models")
auto_import_api = functools.partial(auto_import, "api")
auto_import_admin = functools.partial(auto_import, "admin")
