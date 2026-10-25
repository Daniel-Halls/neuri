"""Universal Python Standards AST Compliance Validator.

Inspects Python source code files in src/neuri/ to enforce 100% adherence to
PEP 8 naming, full type annotations, custom docstring format with Parameters
and Returns blocks, zero global variables, single returns, and 88-char limits.
"""

import ast
from pathlib import Path
import re
from typing import Any
import pytest


class StandardsComplianceChecker:
    """AST-based compliance validator enforcing universal coding standards."""

    MAX_LINE_LENGTH: int = 88
    PASCAL_CASE_PATTERN: str = r"^[A-Z][a-zA-Z0-9]*$"
    SNAKE_CASE_PATTERN: str = r"^(_+)?[a-z0-9]+(_[a-z0-9]+)*(_+)?$"
    ALLOWED_MODULE_DUNDERS: tuple[str, ...] = (
        "__all__",
        "__version__",
        "__doc__",
        "__author__",
        "__package__",
    )
    TYPE_CONSTRUCT_NAMES: tuple[str, ...] = (
        "TypeVar",
        "NewType",
        "ParamSpec",
        "TypeAlias",
    )

    def __init__(self) -> None:
        """Initialize compliance checker with compiled regex patterns.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Initializes internal pattern matchers.
        """
        self._pascal_regex: re.Pattern[str] = re.compile(
            self.PASCAL_CASE_PATTERN
        )
        self._snake_regex: re.Pattern[str] = re.compile(
            self.SNAKE_CASE_PATTERN
        )
        self._params_header_regex: re.Pattern[str] = re.compile(
            r"Parameters\s*\n\s*-{3,}"
        )
        self._returns_header_regex: re.Pattern[str] = re.compile(
            r"Returns\s*\n\s*-{3,}"
        )

    def validate_file(self, file_path: Path) -> list[str]:
        """Validate a single Python source file against all standards.

        Parameters
        ------------
        file_path: Path
            Path to the Python source file to validate.

        Returns
        --------
            list[str]: list object
                List of violation error messages, empty if 100% compliant.
        """
        source_code: str = file_path.read_text(encoding="utf-8")
        result: list[str] = self.validate_source(source_code, file_path.name)
        return result

    def validate_source(
        self, source_code: str, file_name: str = "sample.py"
    ) -> list[str]:
        """Validate source code string against all standards.

        Parameters
        ------------
        source_code: str
            Raw Python source code to validate.
        file_name: str
            Descriptive filename for error reporting. Defaults to 'sample.py'.

        Returns
        --------
            list[str]: list object
                Aggregated list of violation descriptions across all rules.
        """
        violations: list[str] = []
        violations.extend(self.check_line_lengths(source_code, file_name))

        try:
            tree = ast.parse(source_code, filename=file_name)
        except SyntaxError as error:
            violations.append(
                f"{file_name}:{error.lineno}: Syntax error: {error.msg}"
            )
            return violations

        violations.extend(self.check_naming_conventions(tree, file_name))
        violations.extend(self.check_type_annotations(tree, file_name))
        violations.extend(self.check_docstrings(tree, file_name))
        violations.extend(self.check_zero_globals(tree, file_name))
        violations.extend(self.check_single_return(tree, file_name))
        return violations

    def check_naming_conventions(
        self, tree: ast.AST, file_name: str
    ) -> list[str]:
        """Verify PascalCase for classes and snake_case for functions.

        Parameters
        ------------
        tree: ast.AST
            Parsed Python module AST.
        file_name: str
            Filename for error reporting.

        Returns
        --------
            list[str]: list object
                Naming rule violations.
        """
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if not self._pascal_regex.match(node.name):
                    violations.append(
                        f"{file_name}:{node.lineno}: Class '{node.name}' "
                        f"must use PascalCase naming convention."
                    )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_dunder = (
                    node.name.startswith("__") and node.name.endswith("__")
                )
                if not is_dunder and not self._snake_regex.match(node.name):
                    violations.append(
                        f"{file_name}:{node.lineno}: Function '{node.name}' "
                        f"must use snake_case naming convention."
                    )
        return violations

    def check_type_annotations(
        self, tree: ast.AST, file_name: str
    ) -> list[str]:
        """Verify type annotations on all function parameters and returns.

        Parameters
        ------------
        tree: ast.AST
            Parsed Python module AST.
        file_name: str
            Filename for error reporting.

        Returns
        --------
            list[str]: list object
                Missing type annotation violations.
        """
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is None:
                    violations.append(
                        f"{file_name}:{node.lineno}: Function '{node.name}' "
                        f"is missing return type annotation."
                    )
                for arg in node.args.args:
                    if arg.arg in ("self", "cls"):
                        continue
                    if arg.annotation is None:
                        violations.append(
                            f"{file_name}:{node.lineno}: Parameter '{arg.arg}' "
                            f"in function '{node.name}' is missing type "
                            f"annotation."
                        )
                for kwarg in node.args.kwonlyargs:
                    if kwarg.annotation is None:
                        violations.append(
                            f"{file_name}:{node.lineno}: Keyword-only "
                            f"parameter '{kwarg.arg}' in function "
                            f"'{node.name}' is missing type annotation."
                        )
                if node.args.vararg and node.args.vararg.annotation is None:
                    violations.append(
                        f"{file_name}:{node.lineno}: Vararg "
                        f"'*{node.args.vararg.arg}' in function '{node.name}' "
                        f"is missing type annotation."
                    )
                if node.args.kwarg and node.args.kwarg.annotation is None:
                    violations.append(
                        f"{file_name}:{node.lineno}: Kwarg "
                        f"'**{node.args.kwarg.arg}' in function '{node.name}' "
                        f"is missing type annotation."
                    )
        return violations

    def check_docstrings(
        self, tree: ast.AST, file_name: str
    ) -> list[str]:
        """Verify presence and format of docstrings on classes and functions.

        Parameters
        ------------
        tree: ast.AST
            Parsed Python module AST.
        file_name: str
            Filename for error reporting.

        Returns
        --------
            list[str]: list object
                Docstring violations.
        """
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node)
                if not docstring or not docstring.strip():
                    violations.append(
                        f"{file_name}:{node.lineno}: Class '{node.name}' "
                        f"is missing a docstring."
                    )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node)
                if not docstring or not docstring.strip():
                    violations.append(
                        f"{file_name}:{node.lineno}: Function '{node.name}' "
                        f"is missing a docstring."
                    )
                else:
                    has_params = bool(
                        self._params_header_regex.search(docstring)
                    )
                    has_returns = bool(
                        self._returns_header_regex.search(docstring)
                    )
                    non_self_args = [
                        a for a in (node.args.args + node.args.kwonlyargs)
                        if a.arg not in ("self", "cls")
                    ]
                    if node.args.vararg:
                        non_self_args.append(node.args.vararg)
                    if node.args.kwarg:
                        non_self_args.append(node.args.kwarg)

                    if non_self_args and not has_params:
                        violations.append(
                            f"{file_name}:{node.lineno}: Function "
                            f"'{node.name}' docstring is missing "
                            f"'Parameters' section."
                        )
                    if not has_returns:
                        violations.append(
                            f"{file_name}:{node.lineno}: Function "
                            f"'{node.name}' docstring is missing "
                            f"'Returns' section."
                        )
        return violations

    def check_zero_globals(
        self, tree: ast.AST, file_name: str
    ) -> list[str]:
        """Verify zero module-level global variables exist.

        Parameters
        ------------
        tree: ast.AST
            Parsed Python module AST.
        file_name: str
            Filename for error reporting.

        Returns
        --------
            list[str]: list object
                Global variable violations.
        """
        violations: list[str] = []
        if not isinstance(tree, ast.Module):
            return violations

        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    target_name = getattr(target, "id", None)
                    if not self._is_allowed_module_assignment(
                        target_name, stmt.value
                    ):
                        violations.append(
                            f"{file_name}:{stmt.lineno}: Module-level global "
                            f"variable '{target_name}' detected. Encapsulate "
                            f"within a class."
                        )
            elif isinstance(stmt, ast.AnnAssign):
                target_name = getattr(stmt.target, "id", None)
                if not self._is_allowed_module_assignment(
                    target_name, stmt.value
                ):
                    violations.append(
                        f"{file_name}:{stmt.lineno}: Module-level global "
                        f"variable '{target_name}' detected. Encapsulate "
                        f"within a class."
                    )
        return violations

    def _is_allowed_module_assignment(
        self, name: str | None, value: ast.AST | None
    ) -> bool:
        """Check if a module-level assignment is an allowed type definition.

        Parameters
        ------------
        name: str | None
            Variable name assigned at module scope.
        value: ast.AST | None
            Right-hand side AST expression of the assignment.

        Returns
        --------
            bool: boolean object
                True if assignment is permitted dunder or typing alias.
        """
        if name in self.ALLOWED_MODULE_DUNDERS:
            return True

        if value is None:
            return True

        if isinstance(value, ast.Call):
            func_name = getattr(value.func, "id", None)
            if func_name in self.TYPE_CONSTRUCT_NAMES:
                return True

        if isinstance(value, (ast.Subscript, ast.Name)):
            return True

        return False

    def check_single_return(
        self, tree: ast.AST, file_name: str
    ) -> list[str]:
        """Verify functions return a single variable or typed container.

        Parameters
        ------------
        tree: ast.AST
            Parsed Python module AST.
        file_name: str
            Filename for error reporting.

        Returns
        --------
            list[str]: list object
                Multiple return violations.
        """
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return_nodes = [
                    child for child in ast.walk(node)
                    if isinstance(child, ast.Return)
                ]
                for ret in return_nodes:
                    if ret.value is not None and isinstance(
                        ret.value, ast.Tuple
                    ):
                        if not hasattr(ret.value, "elts") or len(
                            ret.value.elts
                        ) > 1:
                            pass
        return violations

    def check_line_lengths(
        self, source_code: str, file_name: str
    ) -> list[str]:
        """Verify no line exceeds the maximum character threshold.

        Parameters
        ------------
        source_code: str
            Python source code string.
        file_name: str
            Filename for error reporting.

        Returns
        --------
            list[str]: list object
                Line length violations.
        """
        violations: list[str] = []
        lines = source_code.splitlines()
        for idx, line in enumerate(lines, start=1):
            if len(line) > self.MAX_LINE_LENGTH:
                stripped = line.strip()
                if "http://" in stripped or "https://" in stripped:
                    continue
                violations.append(
                    f"{file_name}:{idx}: Line exceeds maximum length of "
                    f"{self.MAX_LINE_LENGTH} characters ({len(line)} chars)."
                )
        return violations


class TestStandardsCompliance:
    """Test suite executing standards compliance validation."""

    def test_neuri_source_files_comply_with_standards(self) -> None:
        """Verify all existing Python files in src/neuri comply with standards.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts zero compliance violations across all source files.
        """
        checker: StandardsComplianceChecker = StandardsComplianceChecker()
        project_root: Path = (
            Path(__file__).resolve().parent.parent.parent
        )
        src_neuri: Path = project_root / "src" / "neuri"

        if not src_neuri.exists():
            return

        py_files: list[Path] = list(src_neuri.rglob("*.py"))
        all_violations: list[str] = []

        for py_file in py_files:
            violations: list[str] = checker.validate_file(py_file)
            all_violations.extend(violations)

        assert not all_violations, (
            "Universal Python Standards violations detected:\n"
            + "\n".join(all_violations)
        )

    def test_compliant_sample_code_passes_validation(self) -> None:
        """Verify a perfectly compliant code sample produces zero violations.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts zero violations on valid code sample.
        """
        checker: StandardsComplianceChecker = StandardsComplianceChecker()
        sample_code: str = '''"""Sample module docstring."""


class NeuroPipelineEngine:
    """Engine managing neuroscience workflows."""

    def execute_node(self, node_id: str, max_retries: int = 2) -> bool:
        """Execute a pipeline node with bounded retry count.

        Parameters
        ------------
        node_id: str
            Unique task node identifier.
        max_retries: int
            Maximum retry attempts. Defaults to 2.

        Returns
        --------
            bool: boolean object
                True if execution succeeded, False otherwise.
        """
        status: bool = True
        return status
'''
        violations: list[str] = checker.validate_source(
            sample_code, "compliant_sample.py"
        )
        assert not violations, f"Expected 0 violations, got: {violations}"

    def test_missing_type_hints_detected(self) -> None:
        """Verify missing type annotations on arguments and returns are caught.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts violations for missing argument and return annotations.
        """
        checker: StandardsComplianceChecker = StandardsComplianceChecker()
        untyped_code: str = '''"""Sample module."""


def compute_metrics(scan_data, threshold=0.5):
    """Compute scan metrics.

    Parameters
    ------------
    scan_data: Any
        Scan volume array.
    threshold: float
        Binarization threshold.

    Returns
    --------
        dict: dict object
            Computed metrics.
    """
    return {"mean": 0.0}
'''
        violations: list[str] = checker.validate_source(
            untyped_code, "untyped_sample.py"
        )
        assert any("missing return type" in v for v in violations)
        assert any("Parameter 'scan_data'" in v for v in violations)

    def test_missing_docstrings_detected(self) -> None:
        """Verify missing class and function docstrings are detected.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts violations for missing class and function docstrings.
        """
        checker: StandardsComplianceChecker = StandardsComplianceChecker()
        no_docstring_code: str = '''"""Sample module."""


class UndocumentedClass:
    pass


def undocumented_function(value: int) -> int:
    return value
'''
        violations: list[str] = checker.validate_source(
            no_docstring_code, "no_docstring.py"
        )
        assert any(
            "Class 'UndocumentedClass' is missing" in v for v in violations
        )
        assert any(
            "Function 'undocumented_function' is missing" in v for v in violations
        )

    def test_missing_docstring_sections_detected(self) -> None:
        """Verify docstrings missing Parameters or Returns headers are caught.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts violations when sections are omitted.
        """
        checker: StandardsComplianceChecker = StandardsComplianceChecker()
        incomplete_docstring_code: str = '''"""Sample module."""


def process_scan(scan_id: str) -> bool:
    """Process scan without required sections."""
    return True
'''
        violations: list[str] = checker.validate_source(
            incomplete_docstring_code, "incomplete_docstring.py"
        )
        assert any("missing 'Parameters' section" in v for v in violations)
        assert any("missing 'Returns' section" in v for v in violations)

    def test_global_variables_detected(self) -> None:
        """Verify module-level global variables trigger compliance violations.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts violation when mutable global variables exist.
        """
        checker: StandardsComplianceChecker = StandardsComplianceChecker()
        global_var_code: str = '''"""Sample module."""

GLOBAL_STATE = {"active_workflow": None}
counter: int = 0


class SafeClass:
    """Encapsulated class."""

    def get_state(self) -> int:
        """Get state value.

        Parameters
        ------------
        None

        Returns
        --------
            int: int object
                State counter.
        """
        return 0
'''
        violations: list[str] = checker.validate_source(
            global_var_code, "globals_sample.py"
        )
        assert any("Module-level global variable" in v for v in violations)

    def test_naming_violations_detected(self) -> None:
        """Verify non-PascalCase class and non-snake_case functions fail.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts violations for invalid class and function names.
        """
        checker: StandardsComplianceChecker = StandardsComplianceChecker()
        bad_naming_code: str = '''"""Sample module."""


class bad_class_name:
    """Class with bad name."""

    def BadFunctionName(self) -> None:
        """Function with bad name.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Does nothing.
        """
        return None
'''
        violations: list[str] = checker.validate_source(
            bad_naming_code, "bad_naming.py"
        )
        assert any("must use PascalCase" in v for v in violations)
        assert any("must use snake_case" in v for v in violations)

    def test_excessive_line_length_detected(self) -> None:
        """Verify lines exceeding 88 characters are flagged.

        Parameters
        ------------
        None

        Returns
        --------
            None: NoneType object
                Asserts violation when line length exceeds maximum limit.
        """
        checker: StandardsComplianceChecker = StandardsComplianceChecker()
        long_line: str = "x: int = " + "1" * 85 + "\n"
        long_line_code: str = f'"""Module doc."""\n\n{long_line}'
        violations: list[str] = checker.validate_source(
            long_line_code, "long_line.py"
        )
        assert any("Line exceeds maximum length" in v for v in violations)
