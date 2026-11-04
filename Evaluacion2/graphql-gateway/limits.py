"""Límites de consulta GraphQL: profundidad, costo estimado, campos raíz e introspección.
Se evalúan sobre el AST (después de la validación de esquema) y antes de ejecutar cualquier resolver."""
from graphql import FieldNode, FragmentDefinitionNode, FragmentSpreadNode, InlineFragmentNode, IntValueNode, OperationDefinitionNode, VariableNode


class QueryRejected(Exception):
    def __init__(self, message, code="QUERY_REJECTED"):
        super().__init__(message)
        self.message, self.code = message, code


# campos que devuelven listas: cuánto multiplican el costo de lo que seleccionan
LIST_MULTIPLIER = {"items": 10, "historial": 10}
PAGE_FIELDS = {"misPedidos": (10, 20)}  # campo → (limit por defecto, máximo)


def _multiplier(field: FieldNode) -> int:
    name = field.name.value
    if name in LIST_MULTIPLIER:
        return LIST_MULTIPLIER[name]
    if name in PAGE_FIELDS:
        default, maximum = PAGE_FIELDS[name]
        for arg in field.arguments or ():  # sin argumentos, graphql-core entrega None
            if arg.name.value == "limit":
                if isinstance(arg.value, IntValueNode):
                    return max(1, min(int(arg.value.value), maximum))
                if isinstance(arg.value, VariableNode):
                    return maximum  # no se conoce hasta ejecutar: se asume el peor caso
        return default
    return 1


def check(document, operation_name, *, max_depth, max_cost, max_root_fields, allow_introspection):
    """Lanza QueryRejected si la consulta excede algún límite. Devuelve (profundidad, costo)."""
    fragments = {d.name.value: d for d in document.definitions if isinstance(d, FragmentDefinitionNode)}
    ops = [d for d in document.definitions if isinstance(d, OperationDefinitionNode)]
    if operation_name:
        ops = [o for o in ops if o.name and o.name.value == operation_name]
    if len(ops) != 1:
        raise QueryRejected("Indica una única operación (operationName)")
    op = ops[0]

    def walk(selection_set, depth, seen):
        cost, deepest = 0, depth
        for sel in selection_set.selections:
            if isinstance(sel, FieldNode):
                name = sel.name.value
                if name.startswith("__") and name != "__typename" and not allow_introspection:
                    raise QueryRejected("La introspección está deshabilitada", "INTROSPECTION_DISABLED")
                if sel.selection_set:
                    c, d = walk(sel.selection_set, depth + 1, seen)
                    cost += 1 + _multiplier(sel) * c
                    deepest = max(deepest, d)
                else:
                    cost += 1
                    deepest = max(deepest, depth + 1)
            elif isinstance(sel, FragmentSpreadNode):
                name = sel.name.value
                if name in seen:
                    raise QueryRejected("Fragmentos cíclicos")
                c, d = walk(fragments[name].selection_set, depth, seen | {name})
                cost, deepest = cost + c, max(deepest, d)
            elif isinstance(sel, InlineFragmentNode):
                c, d = walk(sel.selection_set, depth, seen)
                cost, deepest = cost + c, max(deepest, d)
        return cost, deepest

    roots = [s for s in op.selection_set.selections]
    if len(roots) > max_root_fields:
        raise QueryRejected(f"Máximo {max_root_fields} campos raíz por consulta", "TOO_MANY_FIELDS")
    cost, depth = walk(op.selection_set, 0, frozenset())
    if depth > max_depth:
        raise QueryRejected(f"La consulta es demasiado profunda (máximo {max_depth})", "DEPTH_LIMIT")
    if cost > max_cost:
        raise QueryRejected(f"La consulta es demasiado costosa ({cost} > {max_cost})", "COST_LIMIT")
    return depth, cost
