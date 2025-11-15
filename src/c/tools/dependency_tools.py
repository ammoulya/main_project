import os
import pandas as pd
import tomli as toml
import re
import ast
import yaml
import sys
import importlib.util
from crewai.tools import tool

def is_builtin_module(module_name):
    return module_name in sys.builtin_module_names or importlib.util.find_spec(module_name) is None

def split_dependency(dep):
    dep = dep.strip()

    # Remove environment markers (e.g., "; python_version < '3.11'")
    if ";" in dep:
        dep = dep.split(";", 1)[0].strip()

    if "@" in dep:
        package, version = map(str.strip, dep.split("@", 1))
        return package, f"@ {version}"

    match = re.match(r"([\w\-\.]+)(?:\[[^\]]+\])?\s*(==|>=|<=|>|<|~=)?\s*([\d\w\.\*]+)?", dep)
    if match:
        package = match.group(1)
        version_operator = match.group(2) or ""
        version_number = match.group(3) or ""
        version = f"{version_operator}{version_number}".strip() or "latest"
        return package, version

    return dep, "latest"


def parse_setup_py(file_path):
    with open(file_path, 'r') as file:
        setup_content = file.read()
    setup_ast = ast.parse(setup_content)
    install_requires = []
    for node in ast.walk(setup_ast):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'setup':
            for keyword in node.keywords:
                if keyword.arg == 'install_requires' and isinstance(keyword.value, ast.List):
                    install_requires.extend(
                        item.s for item in keyword.value.elts if isinstance(item, ast.Str)
                    )
    return [(file_path,) + split_dependency(dep) for dep in install_requires]

def extract_pipfile_dependencies(pipfile_path):
    dependencies = []
    try:
        pipfile_data = toml.load(pipfile_path)

        if "requires" in pipfile_data:
            python_version = pipfile_data["requires"].get("python_version")
            if python_version:
                dependencies.append((pipfile_path, "python", python_version))

        for section in ["packages", "dev-packages"]:
            if section in pipfile_data:
                for package, version in pipfile_data[section].items():
                    if isinstance(version, dict):
                        version = version.get("version", "")
                    package, version = split_dependency(f"{package} {version}")
                    dependencies.append((pipfile_path, package, version))
    except Exception as e:
        print(f"Error reading Pipfile {pipfile_path}: {e}")
    return dependencies

def extract_pyproject_dependencies(pyproject_path):
    dependencies = []

    with open(pyproject_path, 'r', encoding='utf-8') as f:
        pyproject_data = toml.load(f)

    # ✅ Existing PEP 621 / Poetry standard checks
    if "project" in pyproject_data and "dependencies" in pyproject_data["project"]:
        for dep in pyproject_data["project"]["dependencies"]:
            package, version = split_dependency(dep)
            dependencies.append((pyproject_path, package, version))

    elif "tool" in pyproject_data and "poetry" in pyproject_data["tool"]:
        poetry_deps = pyproject_data["tool"]["poetry"].get("dependencies", {})
        for package, detail in poetry_deps.items():
            if isinstance(detail, str):
                version = detail
            elif isinstance(detail, dict):
                version = detail.get("version", "unspecified")
            else:
                version = "unspecified"
            dependencies.append((pyproject_path, package, version))

    # ✅ ADD THIS fallback check here — your custom non-standard top-level dependencies
    elif "dependencies" in pyproject_data and isinstance(pyproject_data["dependencies"], list):
        for dep in pyproject_data["dependencies"]:
            package, version = split_dependency(dep)
            dependencies.append((pyproject_path, package, version))

    return dependencies



def extract_poetry_lock_dependencies(poetry_lock_path):
    dependencies = []
    try:
        with open(poetry_lock_path, "r", encoding="utf-8") as file:
            poetry_lock_data = toml.load(file)
        for package in poetry_lock_data.get("package", []):
            name = package.get("name", "")
            version = package.get("version", "latest")
            dependencies.append((poetry_lock_path, name, version))
    except Exception as e:
        print(f"Error reading poetry.lock {poetry_lock_path}: {e}")
    return dependencies

def get_conda_dependencies(env_file):
    dependencies = []
    try:
        with open(env_file, "r") as f:
            env_data = yaml.safe_load(f)

            python_version = env_data.get("dependencies", [])
            if isinstance(python_version, list):
                for item in python_version:
                    if isinstance(item, str) and item.startswith("python"):
                        _, version = split_dependency(item)
                        dependencies.append((env_file, "python", version))

            for dep in env_data.get("dependencies", []):
                if isinstance(dep, str):
                    package, version = split_dependency(dep)
                    dependencies.append((env_file, package, version))
                elif isinstance(dep, dict) and "pip" in dep:
                    for pip_dep in dep["pip"]:
                        package, version = split_dependency(pip_dep)
                        dependencies.append((env_file, package, version))
    except Exception as e:
        print(f"Error reading Conda environment file {env_file}: {e}")
    return dependencies

def get_pip_dependencies(requirements_file):
    dependencies = []
    try:
        with open(requirements_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    package, version = split_dependency(line)
                    dependencies.append((requirements_file, package, version))
    except Exception as e:
        print(f"Error reading requirements.txt {requirements_file}: {e}")
    return dependencies

def extract_python_file_dependencies(project_path, python_version):
    dependencies = set()
    pattern = re.compile(r"^\s*(?:import|from)\s+([\w\d_\.]+)")
    for root, _, files in os.walk(project_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            match = pattern.match(line)
                            if match:
                                module = match.group(1).split(".")[0]
                                if not is_builtin_module(module):
                                    dependencies.add((file_path, module, python_version))
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    return list(dependencies)

def find_all_files(root_path, filename):
    matches = []
    for root, _, files in os.walk(root_path):
        for f in files:
            if f.lower() == filename.lower():
                matches.append(os.path.join(root, f))

    return matches

@tool
def extract_project_dependencies(project_path: str) -> str:
    """
    Extract dependencies from all common dependency files and source code within a Python project directory.

    Args:
        project_path (str): The root path of the Python project.

    Returns:
        str: Path to the generated CSV file containing all dependencies.
    """
    dependency_files = {
        "pyproject.toml": extract_pyproject_dependencies,
        "poetry.lock": extract_poetry_lock_dependencies,
        "Pipfile": extract_pipfile_dependencies,
        "environment.yml": get_conda_dependencies,
        "requirements.txt": get_pip_dependencies,
        "setup.py": parse_setup_py,
    }

    all_dependencies = []

    for filename, extractor in dependency_files.items():
        file_paths = find_all_files(project_path, filename)
        for file_path in file_paths:
            try:
                all_dependencies.extend(extractor(file_path))
            except Exception as e:
                print(f"Error extracting from {file_path}: {e}")

    all_dependencies.extend(extract_python_file_dependencies(project_path, "latest"))

    csv_file = os.path.join(project_path, "all_dependencies_with_paths.csv")
    df = pd.DataFrame(all_dependencies, columns=["Source Path", "Package", "Version"])
    df.to_csv(csv_file, index=False)

    return f"Dependencies extracted and saved to {csv_file}"
