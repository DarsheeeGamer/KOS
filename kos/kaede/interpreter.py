"""
Kaede Language Interpreter
==========================

Clean interpreter supporting features from:
- Python: Dynamic execution, built-ins, duck typing
- C++: STL containers, templates, memory management
- Rust: Option/Result types, pattern matching, ownership
"""

import time
import copy
from typing import Dict, List, Any, Optional, Union, Callable
from collections import defaultdict

from .ast_nodes import *
from .runtime import KaedeRuntime
from .core_language import RustOption, RustResult, Vector, Map, Set
from .exceptions import *

class ExecutionContext:
    """Simple execution context for variable scoping"""
    
    def __init__(self, parent: Optional['ExecutionContext'] = None):
        self.parent = parent
        self.variables = {}
        
    def define_variable(self, name: str, value: Any):
        """Define variable in current scope"""
        self.variables[name] = value
    
    def get_variable(self, name: str) -> Any:
        """Get variable value"""
        if name in self.variables:
            return self.variables[name]
        elif self.parent:
            return self.parent.get_variable(name)
        else:
            raise KaedeNameError(name)
    
    def set_variable(self, name: str, value: Any):
        """Set variable value"""
        if name in self.variables:
            self.variables[name] = value
        elif self.parent:
            self.parent.set_variable(name, value)
        else:
            raise KaedeNameError(name)
    
    def create_child_context(self) -> 'ExecutionContext':
        """Create child execution context"""
        return ExecutionContext(parent=self)

class KaedeInterpreter(ASTVisitor):
    """Clean Kaede language interpreter"""
    
    def __init__(self, runtime: KaedeRuntime):
        self.runtime = runtime
        self.global_context = ExecutionContext()
        self.current_context = self.global_context
        
        # Initialize global context with runtime built-ins
        self._initialize_global_context()
    
    def _initialize_global_context(self):
        """Initialize global context with built-in functions"""
        # Copy runtime global scope to interpreter context
        for name, value in self.runtime.global_scope.items():
            self.global_context.define_variable(name, value)
    
    def execute(self, ast_node: ASTNode) -> Any:
        """Execute AST node"""
        try:
            return ast_node.accept(self)
        except Exception as e:
            return self.runtime.handle_exception(e)
    
    def execute_statement(self, stmt: Statement, context: ExecutionContext = None) -> Any:
        """Execute a statement"""
        if context is None:
            context = self.current_context
        
        old_context = self.current_context
        self.current_context = context
        
        try:
            return stmt.accept(self)
        finally:
            self.current_context = old_context
    
    def evaluate_expression(self, expr: Expression, context: ExecutionContext = None) -> Any:
        """Evaluate an expression"""
        if context is None:
            context = self.current_context
        
        old_context = self.current_context
        self.current_context = context
        
        try:
            return expr.accept(self)
        finally:
            self.current_context = old_context
    
    # AST Visitor methods
    def visit_program(self, node: Program) -> Any:
        """Execute program"""
        result = None
        for statement in node.statements:
            result = self.execute_statement(statement)
        return result
    
    def visit_literal(self, node: Literal) -> Any:
        """Visit literal node"""
        return node.value
    
    def visit_identifier(self, node: Identifier) -> Any:
        """Visit identifier node"""
        try:
            return self.current_context.get_variable(node.name)
        except KaedeNameError:
            # Try built-in functions
            if hasattr(self.runtime, f'_builtin_{node.name}'):
                return getattr(self.runtime, f'_builtin_{node.name}')
            raise
    
    def visit_binary_op(self, node: BinaryOp) -> Any:
        """Visit binary operation"""
        left = self.evaluate_expression(node.left)
        right = self.evaluate_expression(node.right)
        
        return self._execute_binary_op(node.operator, left, right)
    
    def _execute_binary_op(self, operator: str, left: Any, right: Any) -> Any:
        """Execute binary operations"""
        try:
            if operator == "+":
                return left + right
            elif operator == "-":
                return left - right
            elif operator == "*":
                return left * right
            elif operator == "/":
                if right == 0:
                    raise KaedeZeroDivisionError()
                return left / right
            elif operator == "//":
                return left // right
            elif operator == "%":
                return left % right
            elif operator == "**":
                return left ** right
            elif operator == "==":
                return left == right
            elif operator == "!=":
                return left != right
            elif operator == "<":
                return left < right
            elif operator == "<=":
                return left <= right
            elif operator == ">":
                return left > right
            elif operator == ">=":
                return left >= right
            elif operator == "and" or operator == "&&":
                return left and right
            elif operator == "or" or operator == "||":
                return left or right
            elif operator == "&":
                return left & right
            elif operator == "|":
                return left | right
            elif operator == "^":
                return left ^ right
            elif operator == "<<":
                return left << right
            elif operator == ">>":
                return left >> right
            else:
                raise KaedeRuntimeError(f"Unknown binary operator: {operator}")
        except Exception as e:
            if not isinstance(e, KaedeError):
                raise KaedeRuntimeError(f"Binary operation error: {e}")
            raise
    
    def visit_unary_op(self, node: UnaryOp) -> Any:
        """Visit unary operation"""
        operand = self.evaluate_expression(node.operand)
        
        if node.operator == "-":
            return -operand
        elif node.operator == "+":
            return +operand
        elif node.operator == "!":
            return not operand
        elif node.operator == "~":
            return ~operand
        elif node.operator == "++":
            if node.prefix:
                new_val = operand + 1
                if isinstance(node.operand, Identifier):
                    self.current_context.set_variable(node.operand.name, new_val)
                return new_val
            else:
                if isinstance(node.operand, Identifier):
                    self.current_context.set_variable(node.operand.name, operand + 1)
                return operand
        elif node.operator == "--":
            if node.prefix:
                new_val = operand - 1
                if isinstance(node.operand, Identifier):
                    self.current_context.set_variable(node.operand.name, new_val)
                return new_val
            else:
                if isinstance(node.operand, Identifier):
                    self.current_context.set_variable(node.operand.name, operand - 1)
                return operand
        else:
            raise KaedeRuntimeError(f"Unknown unary operator: {node.operator}")
    
    def visit_assignment(self, node: Assignment) -> Any:
        """Visit assignment"""
        value = self.evaluate_expression(node.value)
        
        if isinstance(node.target, Identifier):
            if node.operator == "=":
                self.current_context.define_variable(node.target.name, value)
            elif node.operator == "+=":
                current = self.current_context.get_variable(node.target.name)
                self.current_context.set_variable(node.target.name, current + value)
            elif node.operator == "-=":
                current = self.current_context.get_variable(node.target.name)
                self.current_context.set_variable(node.target.name, current - value)
            elif node.operator == "*=":
                current = self.current_context.get_variable(node.target.name)
                self.current_context.set_variable(node.target.name, current * value)
            elif node.operator == "/=":
                current = self.current_context.get_variable(node.target.name)
                self.current_context.set_variable(node.target.name, current / value)
            else:
                raise KaedeRuntimeError(f"Unknown assignment operator: {node.operator}")
        
        return value
    
    def visit_function_call(self, node: FunctionCall) -> Any:
        """Visit function call"""
        function = self.evaluate_expression(node.function)
        arguments = [self.evaluate_expression(arg) for arg in node.arguments]
        
        # Handle special function types
        if isinstance(node.function, Identifier):
            func_name = node.function.name
            
            # Python built-ins
            if func_name in ['print', 'len', 'range', 'list', 'dict', 'str', 'int', 'float', 'bool',
                           'enumerate', 'zip', 'map', 'filter', 'sum', 'min', 'max', 'abs', 'round',
                           'sorted', 'reversed']:
                return self._handle_builtin_function(func_name, arguments)
            
            # C++ STL functions
            elif func_name in ['vector', 'map', 'set', 'unique_ptr', 'shared_ptr', 'find', 'sort',
                             'transform', 'count', 'unique']:
                return self._handle_cpp_function(func_name, arguments)
            
            # Rust functions
            elif func_name in ['Some', 'None', 'Ok', 'Err', 'collect', 'fold', 'take', 'skip']:
                return self._handle_rust_function(func_name, arguments)
        
        # Regular function call
        if callable(function):
            return function(*arguments)
        else:
            raise KaedeTypeError(f"'{function}' is not callable")
    
    def _handle_builtin_function(self, func_name: str, arguments: List[Any]) -> Any:
        """Handle Python built-in function calls"""
        func = getattr(self.runtime, f'_builtin_{func_name}', None)
        if func:
            return func(*arguments)
        else:
            # Try from runtime global scope
            func = self.runtime.global_scope.get(func_name)
            if func and callable(func):
                return func(*arguments)
        raise KaedeNameError(func_name)
    
    def _handle_cpp_function(self, func_name: str, arguments: List[Any]) -> Any:
        """Handle C++ STL function calls"""
        if func_name == 'vector':
            return self.runtime._create_vector(arguments[0] if arguments else None)
        elif func_name == 'map':
            return self.runtime._create_map(arguments[0] if arguments else None)
        elif func_name == 'set':
            return self.runtime._create_set(arguments[0] if arguments else None)
        elif func_name == 'unique_ptr':
            return self.runtime._make_unique(arguments[0] if arguments else None)
        elif func_name == 'shared_ptr':
            return self.runtime._make_shared(arguments[0] if arguments else None)
        elif func_name in ['find', 'sort', 'transform', 'count', 'unique']:
            func = getattr(self.runtime, f'_stl_{func_name}', None)
            if func:
                return func(*arguments)
        
        raise KaedeNameError(func_name)
    
    def _handle_rust_function(self, func_name: str, arguments: List[Any]) -> Any:
        """Handle Rust function calls"""
        if func_name == 'Some':
            return RustOption.Some(arguments[0] if arguments else None)
        elif func_name == 'None':
            return RustOption.None_()
        elif func_name == 'Ok':
            return RustResult.Ok(arguments[0] if arguments else None)
        elif func_name == 'Err':
            return RustResult.Err(arguments[0] if arguments else "Error")
        elif func_name in ['collect', 'fold', 'take', 'skip']:
            func = getattr(self.runtime, f'_rust_{func_name}', None)
            if func:
                return func(*arguments)
        
        raise KaedeNameError(func_name)
    
    def visit_if_statement(self, node: IfStatement) -> Any:
        """Visit if statement"""
        condition = self.evaluate_expression(node.condition)
        
        if condition:
            return self.execute_statement(node.then_statement)
        elif node.else_statement:
            return self.execute_statement(node.else_statement)
        
        return None
    
    def visit_while_loop(self, node: WhileLoop) -> Any:
        """Visit while loop"""
        result = None
        iterations = 0
        max_iterations = 100000  # Prevent infinite loops
        
        while self.evaluate_expression(node.condition) and iterations < max_iterations:
            try:
                result = self.execute_statement(node.body)
                iterations += 1
            except KaedeBreakError:
                break
            except KaedeContinueError:
                continue
        
        if iterations >= max_iterations:
            raise KaedeRuntimeError("Maximum loop iterations exceeded")
        
        return result
    
    def visit_for_loop(self, node: ForLoop) -> Any:
        """Visit for loop"""
        result = None
        
        if node.iterator_var and node.iterable:
            # Python-style for loop
            iterable = self.evaluate_expression(node.iterable)
            
            for item in iterable:
                self.current_context.define_variable(node.iterator_var, item)
                try:
                    result = self.execute_statement(node.body)
                except KaedeBreakError:
                    break
                except KaedeContinueError:
                    continue
        else:
            # C++-style for loop
            if node.init:
                self.execute_statement(node.init)
            
            while True:
                if node.condition and not self.evaluate_expression(node.condition):
                    break
                
                try:
                    result = self.execute_statement(node.body)
                except KaedeBreakError:
                    break
                except KaedeContinueError:
                    pass
                
                if node.update:
                    self.evaluate_expression(node.update)
        
        return result
    
    def visit_return_statement(self, node: ReturnStatement) -> Any:
        """Visit return statement"""
        if node.value:
            value = self.evaluate_expression(node.value)
        else:
            value = None
        
        raise KaedeReturnValue(value)
    
    def visit_break_statement(self, node: BreakStatement) -> Any:
        """Visit break statement"""
        raise KaedeBreakError()
    
    def visit_continue_statement(self, node: ContinueStatement) -> Any:
        """Visit continue statement"""
        raise KaedeContinueError()
    
    def visit_function_declaration(self, node: FunctionDeclaration) -> Any:
        """Visit function declaration"""
        def kaede_function(*args):
            # Create new context for function
            func_context = self.current_context.create_child_context()
            
            # Bind parameters
            for i, param in enumerate(node.parameters):
                if i < len(args):
                    func_context.define_variable(param.name, args[i])
                elif param.default_value:
                    default_val = self.evaluate_expression(param.default_value, func_context)
                    func_context.define_variable(param.name, default_val)
                else:
                    raise KaedeArgumentError(node.name, len(node.parameters), len(args))
            
            # Execute function body
            old_context = self.current_context
            self.current_context = func_context
            
            try:
                self.execute_statement(node.body)
                return None  # No explicit return
            except KaedeReturnValue as ret:
                return ret.value
            finally:
                self.current_context = old_context
        
        # Store function in current context
        self.current_context.define_variable(node.name, kaede_function)
        return kaede_function
    
    def visit_class_declaration(self, node: ClassDeclaration) -> Any:
        """Visit class declaration"""
        class KaedeClass:
            def __init__(self, *args, **kwargs):
                self.__dict__['_kaede_attributes'] = {}
                self.__dict__['_kaede_methods'] = {}
                
                # Execute class body to collect methods and attributes
                class_context = self.current_context.create_child_context()
                old_context = self.current_context
                self.current_context = class_context
                
                try:
                    self.execute_statement(node.body)
                    
                    # Copy class members
                    for name, value in class_context.variables.items():
                        if callable(value):
                            self._kaede_methods[name] = value
                        else:
                            self._kaede_attributes[name] = value
                finally:
                    self.current_context = old_context
            
            def __getattr__(self, name):
                if name in self._kaede_attributes:
                    return self._kaede_attributes[name]
                elif name in self._kaede_methods:
                    return lambda *args, **kwargs: self._kaede_methods[name](self, *args, **kwargs)
                else:
                    raise KaedeAttributeError(type(self).__name__, name)
            
            def __setattr__(self, name, value):
                if name.startswith('_kaede_'):
                    super().__setattr__(name, value)
                else:
                    self._kaede_attributes[name] = value
        
        # Store class in current context
        self.current_context.define_variable(node.name, KaedeClass)
        return KaedeClass
    
    def visit_variable_declaration(self, node: VariableDeclaration) -> Any:
        """Visit variable declaration"""
        if node.initializer:
            value = self.evaluate_expression(node.initializer)
        else:
            value = None
        
        self.current_context.define_variable(node.name, value)
        return value
    
    def visit_block(self, node: Block) -> Any:
        """Visit block statement"""
        result = None
        for statement in node.statements:
            result = self.execute_statement(statement)
        return result
    
    def visit_expression_statement(self, node: ExpressionStatement) -> Any:
        """Visit expression statement"""
        return self.evaluate_expression(node.expression)
    
    def visit_list_literal(self, node: ListLiteral) -> List[Any]:
        """Visit list literal"""
        return [self.evaluate_expression(element) for element in node.elements]
    
    def visit_dict_literal(self, node: DictLiteral) -> Dict[Any, Any]:
        """Visit dictionary literal"""
        result = {}
        for key_expr, value_expr in node.pairs:
            key = self.evaluate_expression(key_expr)
            value = self.evaluate_expression(value_expr)
            result[key] = value
        return result
    
    def visit_array_access(self, node: ArrayAccess) -> Any:
        """Visit array access"""
        array = self.evaluate_expression(node.array)
        index = self.evaluate_expression(node.index)
        
        try:
            return array[index]
        except (IndexError, KeyError) as e:
            if isinstance(e, IndexError):
                raise KaedeIndexError(index, len(array) if hasattr(array, '__len__') else 0)
            else:
                raise KaedeKeyError(str(index))
    
    def visit_member_access(self, node: MemberAccess) -> Any:
        """Visit member access"""
        obj = self.evaluate_expression(node.object)
        
        if hasattr(obj, node.member):
            return getattr(obj, node.member)
        else:
            raise KaedeAttributeError(type(obj).__name__, node.member)
    
    def visit_lambda(self, node: Lambda) -> Callable:
        """Visit lambda expression"""
        def lambda_func(*args):
            # Create lambda context
            lambda_context = self.current_context.create_child_context()
            
            # Bind parameters
            for i, param in enumerate(node.parameters):
                if i < len(args):
                    lambda_context.define_variable(param.name, args[i])
            
            # Execute lambda body
            old_context = self.current_context
            self.current_context = lambda_context
            
            try:
                if isinstance(node.body, Expression):
                    return self.evaluate_expression(node.body)
                else:
                    return self.execute_statement(node.body)
            finally:
                self.current_context = old_context
        
        return lambda_func
    
    # Placeholder implementations for remaining visitor methods
    def visit_method_call(self, node): return None
    def visit_pointer_access(self, node): return None
    def visit_cast(self, node): return None
    def visit_ternary_op(self, node): return None
    def visit_new_expression(self, node): return None
    def visit_delete_expression(self, node): return None
    def visit_move_expression(self, node): return None
    def visit_try_statement(self, node): return None
    def visit_catch_clause(self, node): return None
    def visit_throw_statement(self, node): return None
    def visit_match_statement(self, node): return None
    def visit_match_case(self, node): return None
    def visit_type_annotation(self, node): return None
    def visit_parameter(self, node): return None
    def visit_struct_declaration(self, node): return None
    def visit_field_declaration(self, node): return None
    def visit_enum_declaration(self, node): return None
    def visit_enum_value(self, node): return None
    def visit_namespace_declaration(self, node): return None
    def visit_import_statement(self, node): return None
    def visit_using_statement(self, node): return None

# Special exceptions for control flow
class KaedeReturnValue(Exception):
    """Exception for return values"""
    def __init__(self, value):
        self.value = value
        super().__init__(f"Return: {value}")

class KaedeBreakError(KaedeControlFlowError):
    """Break statement exception"""
    pass

class KaedeContinueError(KaedeControlFlowError):
    """Continue statement exception"""
    pass 