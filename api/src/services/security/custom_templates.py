"""A bounded subset of Jinja for untrusted tenant templates.

No Python objects, calls, arithmetic, macros, imports or recursive loops.
Structural limits bound work before rendering; output is collected incrementally.
"""

from jinja2 import nodes
from jinja2.sandbox import ImmutableSandboxedEnvironment, SecurityError

MAX_SIZE = 512 * 1024
MAX_OUTPUT = 1024 * 1024


class _Environment(ImmutableSandboxedEnvironment):
    def is_safe_attribute(self, obj, attr, value):
        return False

    def is_safe_callable(self, obj):
        return False


def render_custom_template(source: str, context: dict, *, autoescape: bool = True) -> str:
    if len(source.encode("utf-8")) > MAX_SIZE:
        raise SecurityError("Template is too large")
    # Only inert JSON-like values may enter the engine, with bounded collection sizes.
    budget = [0]

    def validate(value, depth=0):
        if depth > 8:
            raise SecurityError("Template data is too deep")
        budget[0] += 1
        if type(value) is str:
            budget[0] += len(value.encode("utf-8"))
        elif type(value) in (list, dict):
            if len(value) > 100:
                raise SecurityError("Template collection is too large")
            for key, item in value.items() if type(value) is dict else enumerate(value):
                if type(value) is dict and type(key) is not str:
                    raise SecurityError("Invalid template key")
                validate(item, depth + 1)
        elif value is not None and type(value) not in (bool, int, float):
            raise SecurityError("Template context must contain plain data")
        if budget[0] > MAX_SIZE:
            raise SecurityError("Template data is too large")

    validate(context)
    env = _Environment(autoescape=autoescape)
    env.globals.clear()
    env.filters = {
        name: env.filters[name] for name in ("escape", "e", "safe", "default", "length", "upper", "lower", "trim")
    }
    env.tests = {name: env.tests[name] for name in ("defined", "undefined", "none")}
    tree = env.parse(source)
    allowed = (
        nodes.Template,
        nodes.Output,
        nodes.TemplateData,
        nodes.Name,
        nodes.Const,
        nodes.Getattr,
        nodes.Getitem,
        nodes.Filter,
        nodes.Test,
        nodes.If,
        nodes.For,
        nodes.Compare,
        nodes.Operand,
        nodes.And,
        nodes.Or,
        nodes.Not,
    )
    all_nodes = [tree, *tree.find_all(nodes.Node)]
    if len(all_nodes) > 1000 or sum(isinstance(n, nodes.For) for n in all_nodes) > 2:
        raise SecurityError("Template is too complex")
    for node in all_nodes:
        if not isinstance(node, allowed) or (isinstance(node, nodes.For) and node.recursive):
            raise SecurityError("Unsupported template operation")
        if isinstance(node, (nodes.Getattr, nodes.Name)) and (
            getattr(node, "attr", getattr(node, "name", "")).startswith("_")
        ):
            raise SecurityError("Private template names are forbidden")

    def bounded_items(value):
        if type(value) not in (list, dict) or len(value) > 100:
            raise SecurityError("Loops require a bounded collection")
        return value

    env.filters["_bounded_items"] = bounded_items
    for node in all_nodes:
        if isinstance(node, nodes.For):
            node.iter = nodes.Filter(node.iter, "_bounded_items", [], [], None, None)
    template = env.from_string(tree)
    chunks, size = [], 0
    for chunk in template.generate(**context):
        size += len(chunk.encode("utf-8"))
        if size > MAX_OUTPUT:
            raise SecurityError("Rendered template is too large")
        chunks.append(chunk)
    return "".join(chunks)
