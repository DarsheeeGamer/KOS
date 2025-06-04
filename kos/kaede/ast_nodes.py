"""
Kaede Language AST Nodes
========================

Abstract Syntax Tree node definitions for Kaede language constructs.
Supports both Python-style and C++-style syntax elements.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from enum import Enum

# Base AST Node
class ASTNode(ABC):
    """Base class for all AST nodes"""
    def __init__(self, line: int = 0, column: int = 0):
        self.line = line
        self.column = column
        self.parent: Optional[ASTNode] = None
        self.children: List[ASTNode] = []
    
    def add_child(self, child: 'ASTNode') -> None:
        """Add a child node"""
        if child:
            child.parent = self
            self.children.append(child)
    
    @abstractmethod
    def accept(self, visitor):
        """Accept a visitor (Visitor pattern)"""
        pass

# Expressions
class Expression(ASTNode):
    """Base class for expressions"""
    pass

class Literal(Expression):
    """Literal values (numbers, strings, booleans, null)"""
    def __init__(self, value: Any, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.value = value
    
    def accept(self, visitor):
        return visitor.visit_literal(self)

class Identifier(Expression):
    """Variable/function/class identifiers"""
    def __init__(self, name: str, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
    
    def accept(self, visitor):
        return visitor.visit_identifier(self)

class BinaryOp(Expression):
    """Binary operations (a + b, a && b, etc.)"""
    def __init__(self, left: Expression, operator: str, right: Expression, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.left = left
        self.operator = operator
        self.right = right
        self.add_child(left)
        self.add_child(right)
    
    def accept(self, visitor):
        return visitor.visit_binary_op(self)

class UnaryOp(Expression):
    """Unary operations (-x, !x, ++x, etc.)"""
    def __init__(self, operator: str, operand: Expression, prefix: bool = True, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.operator = operator
        self.operand = operand
        self.prefix = prefix  # True for prefix (++x), False for postfix (x++)
        self.add_child(operand)
    
    def accept(self, visitor):
        return visitor.visit_unary_op(self)

class Assignment(Expression):
    """Assignment expressions (x = 5, x += 3, etc.)"""
    def __init__(self, target: Expression, operator: str, value: Expression, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.target = target
        self.operator = operator
        self.value = value
        self.add_child(target)
        self.add_child(value)
    
    def accept(self, visitor):
        return visitor.visit_assignment(self)

class FunctionCall(Expression):
    """Function calls (func(a, b, c))"""
    def __init__(self, function: Expression, arguments: List[Expression], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.function = function
        self.arguments = arguments
        self.add_child(function)
        for arg in arguments:
            self.add_child(arg)
    
    def accept(self, visitor):
        return visitor.visit_function_call(self)

class MethodCall(Expression):
    """Method calls (obj.method(a, b))"""
    def __init__(self, object: Expression, method: str, arguments: List[Expression], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.object = object
        self.method = method
        self.arguments = arguments
        self.add_child(object)
        for arg in arguments:
            self.add_child(arg)
    
    def accept(self, visitor):
        return visitor.visit_method_call(self)

class ArrayAccess(Expression):
    """Array/list access (arr[index])"""
    def __init__(self, array: Expression, index: Expression, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.array = array
        self.index = index
        self.add_child(array)
        self.add_child(index)
    
    def accept(self, visitor):
        return visitor.visit_array_access(self)

class MemberAccess(Expression):
    """Member access (obj.member)"""
    def __init__(self, object: Expression, member: str, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.object = object
        self.member = member
        self.add_child(object)
    
    def accept(self, visitor):
        return visitor.visit_member_access(self)

class PointerAccess(Expression):
    """Pointer access (ptr->member)"""
    def __init__(self, pointer: Expression, member: str, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.pointer = pointer
        self.member = member
        self.add_child(pointer)
    
    def accept(self, visitor):
        return visitor.visit_pointer_access(self)

class Cast(Expression):
    """Type casting (int(x), static_cast<int>(x))"""
    def __init__(self, target_type: 'TypeAnnotation', expression: Expression, cast_type: str = "dynamic", line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.target_type = target_type
        self.expression = expression
        self.cast_type = cast_type  # dynamic, static, reinterpret, const
        self.add_child(expression)
    
    def accept(self, visitor):
        return visitor.visit_cast(self)

class Lambda(Expression):
    """Lambda expressions (lambda x: x + 1, [](int x) { return x + 1; })"""
    def __init__(self, parameters: List['Parameter'], body: Union[Expression, 'Block'], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.parameters = parameters
        self.body = body
        for param in parameters:
            self.add_child(param)
        self.add_child(body)
    
    def accept(self, visitor):
        return visitor.visit_lambda(self)

class ListLiteral(Expression):
    """List literals ([1, 2, 3])"""
    def __init__(self, elements: List[Expression], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.elements = elements
        for elem in elements:
            self.add_child(elem)
    
    def accept(self, visitor):
        return visitor.visit_list_literal(self)

class DictLiteral(Expression):
    """Dictionary literals ({key: value})"""
    def __init__(self, pairs: List[tuple[Expression, Expression]], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.pairs = pairs
        for key, value in pairs:
            self.add_child(key)
            self.add_child(value)
    
    def accept(self, visitor):
        return visitor.visit_dict_literal(self)

class TernaryOp(Expression):
    """Ternary operator (condition ? true_expr : false_expr)"""
    def __init__(self, condition: Expression, true_expr: Expression, false_expr: Expression, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.condition = condition
        self.true_expr = true_expr
        self.false_expr = false_expr
        self.add_child(condition)
        self.add_child(true_expr)
        self.add_child(false_expr)
    
    def accept(self, visitor):
        return visitor.visit_ternary_op(self)

# Memory Management Expressions
class NewExpression(Expression):
    """Memory allocation (new Type, new Type[size])"""
    def __init__(self, type_annotation: 'TypeAnnotation', arguments: List[Expression] = None, array_size: Expression = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.type_annotation = type_annotation
        self.arguments = arguments or []
        self.array_size = array_size
        for arg in self.arguments:
            self.add_child(arg)
        if array_size:
            self.add_child(array_size)
    
    def accept(self, visitor):
        return visitor.visit_new_expression(self)

class DeleteExpression(Expression):
    """Memory deallocation (delete ptr, delete[] arr)"""
    def __init__(self, expression: Expression, is_array: bool = False, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.expression = expression
        self.is_array = is_array
        self.add_child(expression)
    
    def accept(self, visitor):
        return visitor.visit_delete_expression(self)

class MoveExpression(Expression):
    """Move semantics (move(obj))"""
    def __init__(self, expression: Expression, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.expression = expression
        self.add_child(expression)
    
    def accept(self, visitor):
        return visitor.visit_move_expression(self)

# Statements
class Statement(ASTNode):
    """Base class for statements"""
    pass

class ExpressionStatement(Statement):
    """Expression used as statement"""
    def __init__(self, expression: Expression, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.expression = expression
        self.add_child(expression)
    
    def accept(self, visitor):
        return visitor.visit_expression_statement(self)

class Block(Statement):
    """Block statement ({ statements })"""
    def __init__(self, statements: List[Statement], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.statements = statements
        for stmt in statements:
            self.add_child(stmt)
    
    def accept(self, visitor):
        return visitor.visit_block(self)

class VariableDeclaration(Statement):
    """Variable declarations (let x: int = 5, var y = 10)"""
    def __init__(self, name: str, type_annotation: Optional['TypeAnnotation'] = None, 
                 initializer: Optional[Expression] = None, is_const: bool = False, 
                 is_mutable: bool = True, storage_class: str = "auto", line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.type_annotation = type_annotation
        self.initializer = initializer
        self.is_const = is_const
        self.is_mutable = is_mutable
        self.storage_class = storage_class  # auto, static, extern, register
        if initializer:
            self.add_child(initializer)
    
    def accept(self, visitor):
        return visitor.visit_variable_declaration(self)

class IfStatement(Statement):
    """If statements"""
    def __init__(self, condition: Expression, then_statement: Statement, 
                 else_statement: Optional[Statement] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.condition = condition
        self.then_statement = then_statement
        self.else_statement = else_statement
        self.add_child(condition)
        self.add_child(then_statement)
        if else_statement:
            self.add_child(else_statement)
    
    def accept(self, visitor):
        return visitor.visit_if_statement(self)

class WhileLoop(Statement):
    """While loops"""
    def __init__(self, condition: Expression, body: Statement, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.condition = condition
        self.body = body
        self.add_child(condition)
        self.add_child(body)
    
    def accept(self, visitor):
        return visitor.visit_while_loop(self)

class ForLoop(Statement):
    """For loops (Python and C++ style)"""
    def __init__(self, init: Optional[Statement], condition: Optional[Expression], 
                 update: Optional[Expression], body: Statement, 
                 iterator_var: Optional[str] = None, iterable: Optional[Expression] = None,
                 line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.init = init  # C++ style
        self.condition = condition  # C++ style
        self.update = update  # C++ style
        self.body = body
        self.iterator_var = iterator_var  # Python style (for x in ...)
        self.iterable = iterable  # Python style
        
        if init:
            self.add_child(init)
        if condition:
            self.add_child(condition)
        if update:
            self.add_child(update)
        if iterable:
            self.add_child(iterable)
        self.add_child(body)
    
    def accept(self, visitor):
        return visitor.visit_for_loop(self)

class ReturnStatement(Statement):
    """Return statements"""
    def __init__(self, value: Optional[Expression] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.value = value
        if value:
            self.add_child(value)
    
    def accept(self, visitor):
        return visitor.visit_return_statement(self)

class BreakStatement(Statement):
    """Break statements"""
    def __init__(self, line: int = 0, column: int = 0):
        super().__init__(line, column)
    
    def accept(self, visitor):
        return visitor.visit_break_statement(self)

class ContinueStatement(Statement):
    """Continue statements"""
    def __init__(self, line: int = 0, column: int = 0):
        super().__init__(line, column)
    
    def accept(self, visitor):
        return visitor.visit_continue_statement(self)

class TryStatement(Statement):
    """Try-catch-finally statements"""
    def __init__(self, try_block: Block, catch_clauses: List['CatchClause'], 
                 finally_block: Optional[Block] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.try_block = try_block
        self.catch_clauses = catch_clauses
        self.finally_block = finally_block
        self.add_child(try_block)
        for clause in catch_clauses:
            self.add_child(clause)
        if finally_block:
            self.add_child(finally_block)
    
    def accept(self, visitor):
        return visitor.visit_try_statement(self)

class CatchClause(ASTNode):
    """Catch clause in try statement"""
    def __init__(self, exception_type: Optional['TypeAnnotation'], variable_name: Optional[str], 
                 body: Block, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.exception_type = exception_type
        self.variable_name = variable_name
        self.body = body
        self.add_child(body)
    
    def accept(self, visitor):
        return visitor.visit_catch_clause(self)

class ThrowStatement(Statement):
    """Throw/raise statements"""
    def __init__(self, expression: Optional[Expression] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.expression = expression
        if expression:
            self.add_child(expression)
    
    def accept(self, visitor):
        return visitor.visit_throw_statement(self)

class MatchStatement(Statement):
    """Pattern matching (match expression with cases)"""
    def __init__(self, expression: Expression, cases: List['MatchCase'], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.expression = expression
        self.cases = cases
        self.add_child(expression)
        for case in cases:
            self.add_child(case)
    
    def accept(self, visitor):
        return visitor.visit_match_statement(self)

class MatchCase(ASTNode):
    """Match case (pattern -> statement)"""
    def __init__(self, pattern: Expression, body: Statement, guard: Optional[Expression] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.pattern = pattern
        self.body = body
        self.guard = guard
        self.add_child(pattern)
        self.add_child(body)
        if guard:
            self.add_child(guard)
    
    def accept(self, visitor):
        return visitor.visit_match_case(self)

# Type System
class TypeAnnotation(ASTNode):
    """Type annotations"""
    def __init__(self, name: str, template_args: List['TypeAnnotation'] = None, 
                 is_pointer: bool = False, is_reference: bool = False, 
                 is_const: bool = False, is_volatile: bool = False, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.template_args = template_args or []
        self.is_pointer = is_pointer
        self.is_reference = is_reference
        self.is_const = is_const
        self.is_volatile = is_volatile
        for arg in self.template_args:
            self.add_child(arg)
    
    def accept(self, visitor):
        return visitor.visit_type_annotation(self)

class Parameter(ASTNode):
    """Function parameter"""
    def __init__(self, name: str, type_annotation: Optional[TypeAnnotation] = None, 
                 default_value: Optional[Expression] = None, is_vararg: bool = False,
                 is_kwarg: bool = False, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.type_annotation = type_annotation
        self.default_value = default_value
        self.is_vararg = is_vararg  # *args
        self.is_kwarg = is_kwarg  # **kwargs
        if default_value:
            self.add_child(default_value)
    
    def accept(self, visitor):
        return visitor.visit_parameter(self)

# Declarations
class FunctionDeclaration(Statement):
    """Function declarations"""
    def __init__(self, name: str, parameters: List[Parameter], return_type: Optional[TypeAnnotation],
                 body: Block, is_async: bool = False, is_virtual: bool = False, 
                 is_static: bool = False, is_inline: bool = False, 
                 template_params: List[str] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.parameters = parameters
        self.return_type = return_type
        self.body = body
        self.is_async = is_async
        self.is_virtual = is_virtual
        self.is_static = is_static
        self.is_inline = is_inline
        self.template_params = template_params or []
        
        for param in parameters:
            self.add_child(param)
        self.add_child(body)
    
    def accept(self, visitor):
        return visitor.visit_function_declaration(self)

class ClassDeclaration(Statement):
    """Class declarations"""
    def __init__(self, name: str, base_classes: List[str], body: Block,
                 template_params: List[str] = None, is_abstract: bool = False,
                 access_specifier: str = "public", line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.base_classes = base_classes
        self.body = body
        self.template_params = template_params or []
        self.is_abstract = is_abstract
        self.access_specifier = access_specifier
        self.add_child(body)
    
    def accept(self, visitor):
        return visitor.visit_class_declaration(self)

class StructDeclaration(Statement):
    """Struct declarations (C++ style)"""
    def __init__(self, name: str, fields: List['FieldDeclaration'], 
                 template_params: List[str] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.fields = fields
        self.template_params = template_params or []
        for field in fields:
            self.add_child(field)
    
    def accept(self, visitor):
        return visitor.visit_struct_declaration(self)

class FieldDeclaration(ASTNode):
    """Class/struct field declaration"""
    def __init__(self, name: str, type_annotation: TypeAnnotation, 
                 initializer: Optional[Expression] = None, access_specifier: str = "public",
                 is_static: bool = False, is_const: bool = False, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.type_annotation = type_annotation
        self.initializer = initializer
        self.access_specifier = access_specifier
        self.is_static = is_static
        self.is_const = is_const
        if initializer:
            self.add_child(initializer)
    
    def accept(self, visitor):
        return visitor.visit_field_declaration(self)

class EnumDeclaration(Statement):
    """Enum declarations"""
    def __init__(self, name: str, values: List['EnumValue'], 
                 underlying_type: Optional[TypeAnnotation] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.values = values
        self.underlying_type = underlying_type
        for value in values:
            self.add_child(value)
    
    def accept(self, visitor):
        return visitor.visit_enum_declaration(self)

class EnumValue(ASTNode):
    """Enum value"""
    def __init__(self, name: str, value: Optional[Expression] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.value = value
        if value:
            self.add_child(value)
    
    def accept(self, visitor):
        return visitor.visit_enum_value(self)

class NamespaceDeclaration(Statement):
    """Namespace declarations"""
    def __init__(self, name: str, body: Block, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.name = name
        self.body = body
        self.add_child(body)
    
    def accept(self, visitor):
        return visitor.visit_namespace_declaration(self)

class ImportStatement(Statement):
    """Import statements"""
    def __init__(self, module: str, items: List[str] = None, alias: Optional[str] = None, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.module = module
        self.items = items or []  # for "from module import item1, item2"
        self.alias = alias  # for "import module as alias"
    
    def accept(self, visitor):
        return visitor.visit_import_statement(self)

class UsingStatement(Statement):
    """Using declarations (C++ style)"""
    def __init__(self, namespace: str, line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.namespace = namespace
    
    def accept(self, visitor):
        return visitor.visit_using_statement(self)

# Root node
class Program(ASTNode):
    """Root AST node representing entire program"""
    def __init__(self, statements: List[Statement], line: int = 0, column: int = 0):
        super().__init__(line, column)
        self.statements = statements
        for stmt in statements:
            self.add_child(stmt)
    
    def accept(self, visitor):
        return visitor.visit_program(self)

# Visitor interface
class ASTVisitor(ABC):
    """Abstract base class for AST visitors"""
    
    @abstractmethod
    def visit_program(self, node: Program): pass
    
    @abstractmethod
    def visit_literal(self, node: Literal): pass
    
    @abstractmethod
    def visit_identifier(self, node: Identifier): pass
    
    @abstractmethod
    def visit_binary_op(self, node: BinaryOp): pass
    
    @abstractmethod
    def visit_unary_op(self, node: UnaryOp): pass
    
    @abstractmethod
    def visit_assignment(self, node: Assignment): pass
    
    @abstractmethod
    def visit_function_call(self, node: FunctionCall): pass
    
    @abstractmethod
    def visit_method_call(self, node: MethodCall): pass
    
    @abstractmethod
    def visit_array_access(self, node: ArrayAccess): pass
    
    @abstractmethod
    def visit_member_access(self, node: MemberAccess): pass
    
    @abstractmethod
    def visit_pointer_access(self, node: PointerAccess): pass
    
    @abstractmethod
    def visit_cast(self, node: Cast): pass
    
    @abstractmethod
    def visit_lambda(self, node: Lambda): pass
    
    @abstractmethod
    def visit_list_literal(self, node: ListLiteral): pass
    
    @abstractmethod
    def visit_dict_literal(self, node: DictLiteral): pass
    
    @abstractmethod
    def visit_ternary_op(self, node: TernaryOp): pass
    
    @abstractmethod
    def visit_new_expression(self, node: NewExpression): pass
    
    @abstractmethod
    def visit_delete_expression(self, node: DeleteExpression): pass
    
    @abstractmethod
    def visit_move_expression(self, node: MoveExpression): pass
    
    @abstractmethod
    def visit_expression_statement(self, node: ExpressionStatement): pass
    
    @abstractmethod
    def visit_block(self, node: Block): pass
    
    @abstractmethod
    def visit_variable_declaration(self, node: VariableDeclaration): pass
    
    @abstractmethod
    def visit_if_statement(self, node: IfStatement): pass
    
    @abstractmethod
    def visit_while_loop(self, node: WhileLoop): pass
    
    @abstractmethod
    def visit_for_loop(self, node: ForLoop): pass
    
    @abstractmethod
    def visit_return_statement(self, node: ReturnStatement): pass
    
    @abstractmethod
    def visit_break_statement(self, node: BreakStatement): pass
    
    @abstractmethod
    def visit_continue_statement(self, node: ContinueStatement): pass
    
    @abstractmethod
    def visit_try_statement(self, node: TryStatement): pass
    
    @abstractmethod
    def visit_catch_clause(self, node: CatchClause): pass
    
    @abstractmethod
    def visit_throw_statement(self, node: ThrowStatement): pass
    
    @abstractmethod
    def visit_match_statement(self, node: MatchStatement): pass
    
    @abstractmethod
    def visit_match_case(self, node: MatchCase): pass
    
    @abstractmethod
    def visit_type_annotation(self, node: TypeAnnotation): pass
    
    @abstractmethod
    def visit_parameter(self, node: Parameter): pass
    
    @abstractmethod
    def visit_function_declaration(self, node: FunctionDeclaration): pass
    
    @abstractmethod
    def visit_class_declaration(self, node: ClassDeclaration): pass
    
    @abstractmethod
    def visit_struct_declaration(self, node: StructDeclaration): pass
    
    @abstractmethod
    def visit_field_declaration(self, node: FieldDeclaration): pass
    
    @abstractmethod
    def visit_enum_declaration(self, node: EnumDeclaration): pass
    
    @abstractmethod
    def visit_enum_value(self, node: EnumValue): pass
    
    @abstractmethod
    def visit_namespace_declaration(self, node: NamespaceDeclaration): pass
    
    @abstractmethod
    def visit_import_statement(self, node: ImportStatement): pass
    
    @abstractmethod
    def visit_using_statement(self, node: UsingStatement): pass

# Aliases for compatibility with compiler
FunctionDeclarationNode = FunctionDeclaration
ClassDeclarationNode = ClassDeclaration
VariableDeclarationNode = VariableDeclaration
IfStatementNode = IfStatement
WhileStatementNode = WhileLoop
ForStatementNode = ForLoop
ReturnStatementNode = ReturnStatement
ExpressionStatementNode = ExpressionStatement
BinaryOpNode = BinaryOp
UnaryOpNode = UnaryOp
FunctionCallNode = FunctionCall
LiteralNode = Literal
IdentifierNode = Identifier
ModuleNode = Program
BlockNode = Block

__all__ = [
    # Base classes
    'ASTNode', 'Expression', 'Statement', 'ASTVisitor',
    
    # Expressions
    'Literal', 'Identifier', 'BinaryOp', 'UnaryOp', 'Assignment', 'FunctionCall',
    'MethodCall', 'ArrayAccess', 'MemberAccess', 'PointerAccess', 'Cast', 'Lambda',
    'ListLiteral', 'DictLiteral', 'TernaryOp', 'NewExpression', 'DeleteExpression',
    'MoveExpression',
    
    # Statements  
    'ExpressionStatement', 'Block', 'VariableDeclaration', 'IfStatement', 'WhileLoop',
    'ForLoop', 'ReturnStatement', 'BreakStatement', 'ContinueStatement', 'TryStatement',
    'ThrowStatement', 'MatchStatement', 'FunctionDeclaration', 'ClassDeclaration',
    'StructDeclaration', 'EnumDeclaration', 'NamespaceDeclaration', 'ImportStatement',
    'UsingStatement',
    
    # Helper classes
    'CatchClause', 'MatchCase', 'TypeAnnotation', 'Parameter', 'FieldDeclaration',
    'EnumValue', 'Program',
    
    # Aliases for compiler compatibility
    'FunctionDeclarationNode', 'ClassDeclarationNode', 'VariableDeclarationNode',
    'IfStatementNode', 'WhileStatementNode', 'ForStatementNode', 'ReturnStatementNode',
    'ExpressionStatementNode', 'BinaryOpNode', 'UnaryOpNode', 'FunctionCallNode',
    'LiteralNode', 'IdentifierNode', 'ModuleNode', 'BlockNode'
] 