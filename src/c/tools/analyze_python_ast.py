import ast
import os
import pandas as pd
import importlib.metadata
from fpdf import FPDF
from crewai.tools import tool

class ImportUsageVisitor(ast.NodeVisitor):
    def __init__(self, source_lines, filename):
        self.source_lines = source_lines
        self.current_file = filename
        self.imports = []
        self.usage = []

    def visit_Import(self, node):
        for alias in node.names:
            code_line = self.source_lines[node.lineno - 1]
            self.imports.append({
                "module": alias.name,
                "alias": alias.asname or alias.name,
                "lineno": node.lineno,
                "code": code_line
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module
        for alias in node.names:
            full_name = f"{module}.{alias.name}"
            code_line = self.source_lines[node.lineno - 1]
            self.imports.append({
                "module": full_name,
                "alias": alias.asname or alias.name,
                "lineno": node.lineno,
                "code": code_line
            })
        self.generic_visit(node)

    def visit_Call(self, node):
        full_name = self.get_full_attribute_name(node.func)
        if full_name:
            line = node.lineno
            code_line = self.source_lines[line - 1]
            self.usage.append((full_name, line, code_line))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        current = node
        while isinstance(current, ast.Attribute):
            current = current.value
        if isinstance(current, ast.Name):
            full_name = self.get_full_attribute_name(node)
            line = node.lineno
            code_line = self.source_lines[line - 1]
            self.usage.append((full_name, line, code_line))
        self.generic_visit(node)

    def get_full_attribute_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self.get_full_attribute_name(node.value)}.{node.attr}"
        return ""

def analyze_repo(repo_path):
    results = []
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.normpath(os.path.join(root, file))
                try:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            source = f.read()
                    except UnicodeDecodeError:
                        print(f"[!] Encoding issue in {file_path}, using fallback decoder.")
                        with open(file_path, "r", encoding="latin-1", errors="replace") as f:
                            source = f.read()

                    source_lines = source.splitlines()
                    tree = ast.parse(source, filename=file_path)
                    visitor = ImportUsageVisitor(source_lines, filename=file_path)
                    visitor.visit(tree)

                    import_map = {imp['alias']: imp for imp in visitor.imports}
                    usage_map = {alias: [] for alias in import_map}

                    for usage, line, code in visitor.usage:
                        root_name = usage.split('.')[0]
                        if root_name in usage_map:
                            usage_map[root_name].append({
                                "symbol": usage,
                                "lineno": line,
                                "code": code
                            })

                    for alias, imp in import_map.items():
                        results.append({
                            "file": file_path,
                            "type": "import",
                            "symbol": imp["module"],
                            "alias": alias,
                            "lineno": imp["lineno"],
                            "code": imp["code"]
                        })
                        for usage in usage_map[alias]:
                            results.append({
                                "file": file_path,
                                "type": "usage",
                                "symbol": usage["symbol"],
                                "alias": alias,
                                "lineno": usage["lineno"],
                                "code": usage["code"]
                            })
                except Exception as e:
                    results.append({
                        "file": file_path,
                        "type": "error",
                        "symbol": str(e),
                        "alias": "",
                        "lineno": -1,
                        "code": ""
                    })
    return results

def safe_text(text):
    return str(text).replace('\t', '    ').encode("latin-1", errors="replace").decode("latin-1")

def load_dependency_versions_with_resolution(csv_path):
    dep_df = pd.read_csv(csv_path)
    resolved_versions = {}
    for _, row in dep_df.iterrows():
        package = row["Package"]
        version = str(row["Version"]).strip().lower()
        if version in ["latest", "python", ""]:
            try:
                resolved_versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                resolved_versions[package] = "latest"
        else:
            resolved_versions[package] = version
    return resolved_versions

def generate_pdf_report(results, project_path, output_file="ast_report.pdf"):
    dependency_versions = load_dependency_versions_with_resolution(
        os.path.join(project_path, "all_dependencies_with_paths.csv")
    )

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "SCA Report", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 7, "Static analysis of Python imports and their usage.")
    pdf.ln(5)

    count = 1
    i = 0
    while i < len(results):
        item = results[i]
        if item["type"] == "import":
            pdf.set_font("Arial", 'B', 11)
            pdf.set_text_color(0, 0, 255)
            symbol = safe_text(item['symbol'])
            alias = safe_text(item['alias'])
            package = symbol.split('.')[0]
            version = dependency_versions.get(package, "unknown")
            pdf.cell(0, 7, f"{count}. {symbol} (version: {version})", ln=True)

            pdf.set_font("Arial", '', 10)
            pdf.set_text_color(0, 0, 0)
            path = safe_text(item['file']).replace("\\", "/")
            pdf.cell(0, 6, f"File Path: {path}", ln=True)
            pdf.cell(0, 6, f"Type: IMPORT", ln=True)
            pdf.cell(0, 6, f"Line: {item['lineno']}", ln=True)
            pdf.cell(0, 6, f"Code: {safe_text(item['code'])}", ln=True)
            pdf.ln(1)

            j = i + 1
            usage_count = 0
            while j < len(results) and results[j]["type"] == "usage" and results[j]["alias"] == item["alias"]:
                usage = results[j]
                if usage_count == 0:
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(0, 6, f"USAGE", ln=True)
                    usage_count += 1
                pdf.set_font("Arial", '', 10)
                pdf.cell(0, 6, f"Line: {usage['lineno']}", ln=True)
                pdf.cell(0, 6, f"Code: {safe_text(usage['code'])}", ln=True)
                pdf.ln(1)
                j += 1
            pdf.ln(2)
            i = j
            count += 1
        else:
            i += 1

    pdf.output(output_file)
    return output_file

@tool
def generate_ast_usage_pdf(project_path: str) -> str:
    """Generate a PDF report showing import usage in Python source files."""
    try:
        print(f"\U0001F50D Scanning project: {project_path}")
        if not os.path.exists(project_path):
            raise FileNotFoundError(f"Project path does not exist: {project_path}")
        results = analyze_repo(project_path)
        if not results:
            raise ValueError("No Python files or analysis results found in the project path.")
        output_pdf = os.path.join(project_path, "ast_report.pdf")
        generate_pdf_report(results, project_path, output_pdf)
        if not os.path.exists(output_pdf):
            raise IOError("PDF file was not created.")
        print(f"\u2705 PDF generated: {output_pdf}")
        return f"AST usage report saved to: {output_pdf}"
    except Exception as e:
        error_message = f"\u274C Error generating PDF: {str(e)}"
        print(error_message)
        return error_message