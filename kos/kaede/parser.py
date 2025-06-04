"""
Kaede Language Parser
====================

Recursive descent parser for Kaede language supporting:
- Python-style syntax (indentation-based blocks)
- C++-style syntax (brace-based blocks)
- Hybrid type annotations
- Template/generic syntax
- Modern language features
"""

from typing import List, Optional, Union, Dict, Any
from .lexer import Token, TokenType, KaedeLexer
from .ast_nodes import *
from .exceptions import KaedeSyntaxError, KaedeError

class KaedeParser:
    """Recursive descent parser for Kaede language"""
    
    def __init__(self):
        self.tokens: List[Token] = []
        self.current = 0
        self.filename = "<unknown>"
        
    def error(self, message: str, token: Optional[Token] = None) -> None:
        """Raise a syntax error"""
        if token is None:
            token = self.peek()
        raise KaedeSyntaxError(message, token.line, token.column, self.filename)
        
    def peek(self, offset: int = 0) -> Token:
        """Peek at token at current position + offset"""
        pos = self.current + offset
        if pos >= len(self.tokens):
            return self.tokens[-1]  # EOF token
        return self.tokens[pos]
        
    def advance(self) -> Token:
        """Consume and return current token"""
        if not self.is_at_end():
            self.current += 1
        return self.previous()
        
    def previous(self) -> Token:
        """Return previous token"""
        return self.tokens[self.current - 1]
        
    def is_at_end(self) -> bool:
        """Check if at end of tokens"""
        return self.peek().type == TokenType.EOF
        
    def check(self, token_type: TokenType) -> bool:
        """Check if current token is of given type"""
        if self.is_at_end():
            return False
        return self.peek().type == token_type
        
    def match(self, *types: TokenType) -> bool:
        """Check if current token matches any of the given types"""
        for token_type in types:
            if self.check(token_type):
                self.advance()
                return True
        return False
        
    def consume(self, token_type: TokenType, message: str) -> Token:
        """Consume token of expected type or raise error"""
        if self.check(token_type):
            return self.advance()
        self.error(message)
        
    def synchronize(self) -> None:
        """Synchronize parser after error"""
        self.advance()
        
        while not self.is_at_end():
            if self.previous().type == TokenType.SEMICOLON:
                return
                
            if self.peek().type in [
                TokenType.CLASS, TokenType.DEF, TokenType.VAR, TokenType.FOR,
                TokenType.IF, TokenType.WHILE, TokenType.RETURN, TokenType.STRUCT,
                TokenType.ENUM, TokenType.NAMESPACE
            ]:
                return
                
            self.advance()
    
    def parse(self, tokens: List[Token], filename: str = "<unknown>") -> Program:
        """Parse tokens into AST"""
        self.tokens = tokens
        self.current = 0
        self.filename = filename
        
        statements = []
        while not self.is_at_end():
            try:
                stmt = self.declaration()
                if stmt:
                    statements.append(stmt)
            except KaedeError as e:
                # Error recovery
                print(f"Parse error: {e}")
                self.synchronize()
                
        return Program(statements)
    
    def declaration(self) -> Optional[Statement]:
        """Parse declarations"""
        try:
            # Skip comments and newlines
            while self.match(TokenType.COMMENT, TokenType.MULTILINE_COMMENT, TokenType.NEWLINE):
                pass
                
            if self.is_at_end():
                return None
                
            # Template declarations
            if self.check(TokenType.TEMPLATE):
                return self.template_declaration()
                
            # Namespace declarations
            if self.match(TokenType.NAMESPACE):
                return self.namespace_declaration()
                
            # Class declarations
            if self.match(TokenType.CLASS):
                return self.class_declaration()
                
            # Struct declarations
            if self.match(TokenType.STRUCT):
                return self.struct_declaration()
                
            # Enum declarations
            if self.match(TokenType.ENUM):
                return self.enum_declaration()
                
            # Function declarations
            if self.check(TokenType.DEF) or self.check_function_signature():
                return self.function_declaration()
                
            # Variable declarations
            if self.match(TokenType.LET, TokenType.VAR, TokenType.CONST, TokenType.STATIC):
                return self.variable_declaration(self.previous().type)
                
            # Import/using statements
            if self.match(TokenType.IMPORT):
                return self.import_statement()
            if self.match(TokenType.FROM):
                return self.from_import_statement()
            if self.match(TokenType.USING):
                return self.using_statement()
                
            # Regular statements
            return self.statement()
            
        except KaedeError as e:
            self.synchronize()
            raise e
    
    def check_function_signature(self) -> bool:
        """Check if current position looks like a function signature"""
        # Look for patterns like: identifier(params) -> type or identifier(params) :
        saved_pos = self.current
        try:
            if not self.check(TokenType.IDENTIFIER):
                return False
            self.advance()  # identifier
            
            if not self.check(TokenType.LEFT_PAREN):
                return False
            self.advance()  # (
            
            # Skip parameter list
            depth = 1
            while depth > 0 and not self.is_at_end():
                if self.check(TokenType.LEFT_PAREN):
                    depth += 1
                elif self.check(TokenType.RIGHT_PAREN):
                    depth -= 1
                self.advance()
            
            # Check for return type annotation or colon
            result = self.check(TokenType.ARROW) or self.check(TokenType.COLON)
            return result
        finally:
            self.current = saved_pos
    
    def template_declaration(self) -> Statement:
        """Parse template declarations"""
        self.consume(TokenType.TEMPLATE, "Expected 'template'")
        self.consume(TokenType.LEFT_ANGLE, "Expected '<' after 'template'")
        
        template_params = []
        while not self.check(TokenType.RIGHT_ANGLE) and not self.is_at_end():
            if self.match(TokenType.TYPENAME, TokenType.CLASS):
                param_name = self.consume(TokenType.IDENTIFIER, "Expected template parameter name").value
                template_params.append(param_name)
            else:
                self.error("Expected 'typename' or 'class' in template parameter")
                
            if not self.check(TokenType.RIGHT_ANGLE):
                self.consume(TokenType.COMMA, "Expected ',' between template parameters")
        
        self.consume(TokenType.RIGHT_ANGLE, "Expected '>' after template parameters")
        
        # Parse the templated declaration
        declaration = self.declaration()
        
        # Add template parameters to the declaration
        if isinstance(declaration, (FunctionDeclaration, ClassDeclaration, StructDeclaration)):
            declaration.template_params = template_params
        else:
            self.error("Templates can only be applied to functions, classes, or structs")
            
        return declaration
    
    def namespace_declaration(self) -> NamespaceDeclaration:
        """Parse namespace declarations"""
        name = self.consume(TokenType.IDENTIFIER, "Expected namespace name").value
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after namespace name")
        
        statements = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            stmt = self.declaration()
            if stmt:
                statements.append(stmt)
        
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after namespace body")
        return NamespaceDeclaration(name, Block(statements))
    
    def class_declaration(self) -> ClassDeclaration:
        """Parse class declarations"""
        name = self.consume(TokenType.IDENTIFIER, "Expected class name").value
        
        # Parse base classes
        base_classes = []
        if self.match(TokenType.COLON):
            while True:
                access = "public"  # default
                if self.match(TokenType.PUBLIC, TokenType.PRIVATE, TokenType.PROTECTED):
                    access = self.previous().value
                    
                base_name = self.consume(TokenType.IDENTIFIER, "Expected base class name").value
                base_classes.append(f"{access} {base_name}")
                
                if not self.match(TokenType.COMMA):
                    break
        
        # Parse class body
        if self.match(TokenType.COLON):
            # Python-style class body
            self.consume(TokenType.NEWLINE, "Expected newline after class header")
            self.consume(TokenType.INDENT, "Expected indented class body")
            
            statements = []
            while not self.check(TokenType.DEDENT) and not self.is_at_end():
                stmt = self.declaration()
                if stmt:
                    statements.append(stmt)
            
            self.consume(TokenType.DEDENT, "Expected dedent after class body")
            body = Block(statements)
        else:
            # C++-style class body
            self.consume(TokenType.LEFT_BRACE, "Expected '{' or ':' after class header")
            
            statements = []
            while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
                stmt = self.declaration()
                if stmt:
                    statements.append(stmt)
            
            self.consume(TokenType.RIGHT_BRACE, "Expected '}' after class body")
            body = Block(statements)
        
        return ClassDeclaration(name, base_classes, body)
    
    def struct_declaration(self) -> StructDeclaration:
        """Parse struct declarations"""
        name = self.consume(TokenType.IDENTIFIER, "Expected struct name").value
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after struct name")
        
        fields = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            field = self.field_declaration()
            fields.append(field)
        
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after struct body")
        self.match(TokenType.SEMICOLON)  # Optional semicolon
        
        return StructDeclaration(name, fields)
    
    def field_declaration(self) -> FieldDeclaration:
        """Parse field declarations"""
        # Access specifier
        access = "public"
        if self.match(TokenType.PUBLIC, TokenType.PRIVATE, TokenType.PROTECTED):
            access = self.previous().value
            self.consume(TokenType.COLON, "Expected ':' after access specifier")
        
        # Static/const modifiers
        is_static = self.match(TokenType.STATIC)
        is_const = self.match(TokenType.CONST)
        
        # Type and name
        type_annotation = self.type_annotation()
        name = self.consume(TokenType.IDENTIFIER, "Expected field name").value
        
        # Optional initializer
        initializer = None
        if self.match(TokenType.ASSIGN):
            initializer = self.expression()
        
        self.consume(TokenType.SEMICOLON, "Expected ';' after field declaration")
        
        return FieldDeclaration(name, type_annotation, initializer, access, is_static, is_const)
    
    def enum_declaration(self) -> EnumDeclaration:
        """Parse enum declarations"""
        name = self.consume(TokenType.IDENTIFIER, "Expected enum name").value
        
        # Optional underlying type
        underlying_type = None
        if self.match(TokenType.COLON):
            underlying_type = self.type_annotation()
        
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after enum header")
        
        values = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            enum_name = self.consume(TokenType.IDENTIFIER, "Expected enum value name").value
            
            enum_value = None
            if self.match(TokenType.ASSIGN):
                enum_value = self.expression()
            
            values.append(EnumValue(enum_name, enum_value))
            
            if not self.check(TokenType.RIGHT_BRACE):
                self.consume(TokenType.COMMA, "Expected ',' between enum values")
        
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after enum body")
        self.match(TokenType.SEMICOLON)  # Optional semicolon
        
        return EnumDeclaration(name, values, underlying_type)
    
    def function_declaration(self) -> FunctionDeclaration:
        """Parse function declarations"""
        # Function modifiers
        is_async = False
        is_virtual = False
        is_static = False
        is_inline = False
        
        while self.match(TokenType.ASYNC, TokenType.VIRTUAL, TokenType.STATIC, TokenType.INLINE):
            token_type = self.previous().type
            if token_type == TokenType.ASYNC:
                is_async = True
            elif token_type == TokenType.VIRTUAL:
                is_virtual = True
            elif token_type == TokenType.STATIC:
                is_static = True
            elif token_type == TokenType.INLINE:
                is_inline = True
        
        # 'def' keyword (optional for C++ style)
        self.match(TokenType.DEF)
        
        # Function name
        name = self.consume(TokenType.IDENTIFIER, "Expected function name").value
        
        # Parameters
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after function name")
        parameters = self.parameter_list()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after parameters")
        
        # Return type
        return_type = None
        if self.match(TokenType.ARROW, TokenType.COLON):
            return_type = self.type_annotation()
        
        # Function body
        if self.match(TokenType.COLON):
            # Python-style function body
            self.consume(TokenType.NEWLINE, "Expected newline after function header")
            self.consume(TokenType.INDENT, "Expected indented function body")
            
            statements = []
            while not self.check(TokenType.DEDENT) and not self.is_at_end():
                stmt = self.statement()
                if stmt:
                    statements.append(stmt)
            
            self.consume(TokenType.DEDENT, "Expected dedent after function body")
            body = Block(statements)
        else:
            # C++-style function body
            self.consume(TokenType.LEFT_BRACE, "Expected '{' or ':' for function body")
            
            statements = []
            while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
                stmt = self.statement()
                if stmt:
                    statements.append(stmt)
            
            self.consume(TokenType.RIGHT_BRACE, "Expected '}' after function body")
            body = Block(statements)
        
        return FunctionDeclaration(name, parameters, return_type, body, 
                                 is_async, is_virtual, is_static, is_inline)
    
    def parameter_list(self) -> List[Parameter]:
        """Parse function parameter list"""
        parameters = []
        
        while not self.check(TokenType.RIGHT_PAREN) and not self.is_at_end():
            # Varargs (*args)
            is_vararg = self.match(TokenType.MULTIPLY)
            # Kwargs (**kwargs)
            is_kwarg = self.match(TokenType.POWER)
            
            param_name = self.consume(TokenType.IDENTIFIER, "Expected parameter name").value
            
            # Type annotation
            type_annotation = None
            if self.match(TokenType.COLON):
                type_annotation = self.type_annotation()
            
            # Default value
            default_value = None
            if self.match(TokenType.ASSIGN):
                default_value = self.expression()
            
            parameters.append(Parameter(param_name, type_annotation, default_value, is_vararg, is_kwarg))
            
            if not self.check(TokenType.RIGHT_PAREN):
                self.consume(TokenType.COMMA, "Expected ',' between parameters")
        
        return parameters
    
    def variable_declaration(self, keyword_type: TokenType) -> VariableDeclaration:
        """Parse variable declarations"""
        is_const = keyword_type == TokenType.CONST
        is_mutable = keyword_type != TokenType.CONST
        storage_class = "auto"
        
        if keyword_type == TokenType.STATIC:
            storage_class = "static"
        
        var_name = self.consume(TokenType.IDENTIFIER, "Expected variable name").value
        
        # Type annotation
        type_annotation = None
        if self.match(TokenType.COLON):
            type_annotation = self.type_annotation()
        
        # Initializer
        initializer = None
        if self.match(TokenType.ASSIGN):
            initializer = self.expression()
        elif is_const:
            self.error("Const variables must be initialized")
        
        self.match(TokenType.SEMICOLON, TokenType.NEWLINE)  # Optional
        
        return VariableDeclaration(var_name, type_annotation, initializer, 
                                 is_const, is_mutable, storage_class)
    
    def import_statement(self) -> ImportStatement:
        """Parse import statements"""
        module = self.consume(TokenType.IDENTIFIER, "Expected module name").value
        
        # Handle dotted module names
        while self.match(TokenType.DOT):
            module += "." + self.consume(TokenType.IDENTIFIER, "Expected module name").value
        
        alias = None
        if self.match(TokenType.AS):
            alias = self.consume(TokenType.IDENTIFIER, "Expected alias name").value
        
        self.match(TokenType.NEWLINE, TokenType.SEMICOLON)
        return ImportStatement(module, alias=alias)
    
    def from_import_statement(self) -> ImportStatement:
        """Parse from...import statements"""
        module = self.consume(TokenType.IDENTIFIER, "Expected module name").value
        
        # Handle dotted module names
        while self.match(TokenType.DOT):
            module += "." + self.consume(TokenType.IDENTIFIER, "Expected module name").value
        
        self.consume(TokenType.IMPORT, "Expected 'import' after module name")
        
        items = []
        while True:
            item = self.consume(TokenType.IDENTIFIER, "Expected import item").value
            items.append(item)
            
            if not self.match(TokenType.COMMA):
                break
        
        self.match(TokenType.NEWLINE, TokenType.SEMICOLON)
        return ImportStatement(module, items)
    
    def using_statement(self) -> UsingStatement:
        """Parse using statements (C++ style)"""
        if self.match(TokenType.NAMESPACE):
            namespace = self.consume(TokenType.IDENTIFIER, "Expected namespace name").value
            self.consume(TokenType.SEMICOLON, "Expected ';' after using statement")
            return UsingStatement(namespace)
        else:
            self.error("Expected 'namespace' after 'using'")
    
    def statement(self) -> Optional[Statement]:
        """Parse statements"""
        # Skip newlines and comments
        while self.match(TokenType.NEWLINE, TokenType.COMMENT, TokenType.MULTILINE_COMMENT):
            pass
            
        if self.is_at_end():
            return None
        
        # Control flow statements
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.FOR):
            return self.for_statement()
        if self.match(TokenType.MATCH):
            return self.match_statement()
        
        # Jump statements
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.BREAK):
            return self.break_statement()
        if self.match(TokenType.CONTINUE):
            return self.continue_statement()
        
        # Exception handling
        if self.match(TokenType.TRY):
            return self.try_statement()
        if self.match(TokenType.RAISE, TokenType.THROW):
            return self.throw_statement()
        
        # Block statements
        if self.check(TokenType.LEFT_BRACE):
            return self.block_statement()
        
        # Expression statements
        return self.expression_statement()
    
    def if_statement(self) -> IfStatement:
        """Parse if statements"""
        condition = self.expression()
        
        # Parse then block
        then_stmt = self.statement_block()
        
        # Parse else/elif
        else_stmt = None
        if self.match(TokenType.ELIF):
            else_stmt = self.if_statement()  # Recursive for elif chain
        elif self.match(TokenType.ELSE):
            else_stmt = self.statement_block()
        
        return IfStatement(condition, then_stmt, else_stmt)
    
    def while_statement(self) -> WhileLoop:
        """Parse while statements"""
        condition = self.expression()
        body = self.statement_block()
        return WhileLoop(condition, body)
    
    def for_statement(self) -> ForLoop:
        """Parse for statements (both Python and C++ style)"""
        # Check for Python-style for loop (for x in ...)
        if self.check(TokenType.IDENTIFIER):
            saved_pos = self.current
            try:
                var_name = self.advance().value
                if self.match(TokenType.IN):
                    # Python-style for loop
                    iterable = self.expression()
                    body = self.statement_block()
                    return ForLoop(None, None, None, body, var_name, iterable)
                else:
                    # Reset and parse as C++-style
                    self.current = saved_pos
            except:
                self.current = saved_pos
        
        # C++-style for loop
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after 'for'")
        
        # Init statement
        init = None
        if not self.check(TokenType.SEMICOLON):
            init = self.statement()
        self.consume(TokenType.SEMICOLON, "Expected ';' after for loop init")
        
        # Condition
        condition = None
        if not self.check(TokenType.SEMICOLON):
            condition = self.expression()
        self.consume(TokenType.SEMICOLON, "Expected ';' after for loop condition")
        
        # Update expression
        update = None
        if not self.check(TokenType.RIGHT_PAREN):
            update = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after for loop header")
        
        body = self.statement_block()
        return ForLoop(init, condition, update, body)
    
    def match_statement(self) -> MatchStatement:
        """Parse match statements (pattern matching)"""
        expression = self.expression()
        
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after match expression")
        
        cases = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            pattern = self.expression()
            
            # Optional guard
            guard = None
            if self.match(TokenType.IF):
                guard = self.expression()
            
            self.consume(TokenType.ARROW, "Expected '->' after match pattern")
            body = self.statement()
            
            cases.append(MatchCase(pattern, body, guard))
            
            self.match(TokenType.COMMA)  # Optional comma
        
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after match cases")
        return MatchStatement(expression, cases)
    
    def return_statement(self) -> ReturnStatement:
        """Parse return statements"""
        value = None
        if not self.check(TokenType.NEWLINE) and not self.check(TokenType.SEMICOLON):
            value = self.expression()
        
        self.match(TokenType.NEWLINE, TokenType.SEMICOLON)
        return ReturnStatement(value)
    
    def break_statement(self) -> BreakStatement:
        """Parse break statements"""
        self.match(TokenType.NEWLINE, TokenType.SEMICOLON)
        return BreakStatement()
    
    def continue_statement(self) -> ContinueStatement:
        """Parse continue statements"""
        self.match(TokenType.NEWLINE, TokenType.SEMICOLON)
        return ContinueStatement()
    
    def try_statement(self) -> TryStatement:
        """Parse try-catch-finally statements"""
        try_block = self.block_statement()
        
        catch_clauses = []
        while self.match(TokenType.EXCEPT, TokenType.CATCH):
            exception_type = None
            variable_name = None
            
            if not self.check(TokenType.COLON) and not self.check(TokenType.LEFT_BRACE):
                exception_type = self.type_annotation()
                
                if self.match(TokenType.AS):
                    variable_name = self.consume(TokenType.IDENTIFIER, "Expected variable name").value
            
            catch_body = self.block_statement()
            catch_clauses.append(CatchClause(exception_type, variable_name, catch_body))
        
        finally_block = None
        if self.match(TokenType.FINALLY):
            finally_block = self.block_statement()
        
        return TryStatement(try_block, catch_clauses, finally_block)
    
    def throw_statement(self) -> ThrowStatement:
        """Parse throw/raise statements"""
        expression = None
        if not self.check(TokenType.NEWLINE) and not self.check(TokenType.SEMICOLON):
            expression = self.expression()
        
        self.match(TokenType.NEWLINE, TokenType.SEMICOLON)
        return ThrowStatement(expression)
    
    def block_statement(self) -> Block:
        """Parse block statements"""
        self.consume(TokenType.LEFT_BRACE, "Expected '{'")
        
        statements = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            stmt = self.statement()
            if stmt:
                statements.append(stmt)
        
        self.consume(TokenType.RIGHT_BRACE, "Expected '}'")
        return Block(statements)
    
    def statement_block(self) -> Statement:
        """Parse statement block (either brace-style or Python-style)"""
        if self.match(TokenType.COLON):
            # Python-style indented block
            self.consume(TokenType.NEWLINE, "Expected newline after ':'")
            self.consume(TokenType.INDENT, "Expected indented block")
            
            statements = []
            while not self.check(TokenType.DEDENT) and not self.is_at_end():
                stmt = self.statement()
                if stmt:
                    statements.append(stmt)
            
            self.consume(TokenType.DEDENT, "Expected dedent")
            return Block(statements)
        else:
            # Single statement or brace block
            return self.statement()
    
    def expression_statement(self) -> ExpressionStatement:
        """Parse expression statements"""
        expr = self.expression()
        self.match(TokenType.NEWLINE, TokenType.SEMICOLON)
        return ExpressionStatement(expr)
    
    # Expression parsing with operator precedence
    def expression(self) -> Expression:
        """Parse expressions"""
        return self.ternary()
    
    def ternary(self) -> Expression:
        """Parse ternary operator (condition ? true : false)"""
        expr = self.logical_or()
        
        if self.match(TokenType.QUESTION):
            true_expr = self.expression()
            self.consume(TokenType.COLON, "Expected ':' after ternary true expression")
            false_expr = self.expression()
            return TernaryOp(expr, true_expr, false_expr)
        
        return expr
    
    def logical_or(self) -> Expression:
        """Parse logical OR expressions"""
        expr = self.logical_and()
        
        while self.match(TokenType.OR, TokenType.LOGICAL_OR):
            operator = self.previous().value
            right = self.logical_and()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def logical_and(self) -> Expression:
        """Parse logical AND expressions"""
        expr = self.equality()
        
        while self.match(TokenType.AND, TokenType.LOGICAL_AND):
            operator = self.previous().value
            right = self.equality()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def equality(self) -> Expression:
        """Parse equality expressions"""
        expr = self.comparison()
        
        while self.match(TokenType.EQUAL, TokenType.NOT_EQUAL):
            operator = self.previous().value
            right = self.comparison()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def comparison(self) -> Expression:
        """Parse comparison expressions"""
        expr = self.bitwise_or()
        
        while self.match(TokenType.GREATER_THAN, TokenType.GREATER_EQUAL,
                         TokenType.LESS_THAN, TokenType.LESS_EQUAL, TokenType.SPACESHIP):
            operator = self.previous().value
            right = self.bitwise_or()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def bitwise_or(self) -> Expression:
        """Parse bitwise OR expressions"""
        expr = self.bitwise_xor()
        
        while self.match(TokenType.BITWISE_OR):
            operator = self.previous().value
            right = self.bitwise_xor()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def bitwise_xor(self) -> Expression:
        """Parse bitwise XOR expressions"""
        expr = self.bitwise_and()
        
        while self.match(TokenType.BITWISE_XOR):
            operator = self.previous().value
            right = self.bitwise_and()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def bitwise_and(self) -> Expression:
        """Parse bitwise AND expressions"""
        expr = self.shift()
        
        while self.match(TokenType.BITWISE_AND):
            operator = self.previous().value
            right = self.shift()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def shift(self) -> Expression:
        """Parse shift expressions"""
        expr = self.addition()
        
        while self.match(TokenType.LEFT_SHIFT, TokenType.RIGHT_SHIFT):
            operator = self.previous().value
            right = self.addition()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def addition(self) -> Expression:
        """Parse addition/subtraction expressions"""
        expr = self.multiplication()
        
        while self.match(TokenType.PLUS, TokenType.MINUS):
            operator = self.previous().value
            right = self.multiplication()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def multiplication(self) -> Expression:
        """Parse multiplication/division expressions"""
        expr = self.unary()
        
        while self.match(TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO, 
                         TokenType.FLOOR_DIVIDE):
            operator = self.previous().value
            right = self.unary()
            expr = BinaryOp(expr, operator, right)
        
        return expr
    
    def unary(self) -> Expression:
        """Parse unary expressions"""
        if self.match(TokenType.LOGICAL_NOT, TokenType.MINUS, TokenType.PLUS, 
                      TokenType.BITWISE_NOT, TokenType.INCREMENT, TokenType.DECREMENT):
            operator = self.previous().value
            expr = self.unary()
            return UnaryOp(operator, expr, prefix=True)
        
        return self.power()
    
    def power(self) -> Expression:
        """Parse power expressions"""
        expr = self.postfix()
        
        if self.match(TokenType.POWER):
            operator = self.previous().value
            right = self.unary()  # Right associative
            return BinaryOp(expr, operator, right)
        
        return expr
    
    def postfix(self) -> Expression:
        """Parse postfix expressions"""
        expr = self.primary()
        
        while True:
            if self.match(TokenType.LEFT_PAREN):
                # Function call
                args = []
                while not self.check(TokenType.RIGHT_PAREN) and not self.is_at_end():
                    args.append(self.expression())
                    if not self.check(TokenType.RIGHT_PAREN):
                        self.consume(TokenType.COMMA, "Expected ',' between arguments")
                
                self.consume(TokenType.RIGHT_PAREN, "Expected ')' after arguments")
                expr = FunctionCall(expr, args)
                
            elif self.match(TokenType.LEFT_BRACKET):
                # Array access
                index = self.expression()
                self.consume(TokenType.RIGHT_BRACKET, "Expected ']' after array index")
                expr = ArrayAccess(expr, index)
                
            elif self.match(TokenType.DOT):
                # Member access
                member = self.consume(TokenType.IDENTIFIER, "Expected member name").value
                if self.check(TokenType.LEFT_PAREN):
                    # Method call
                    self.advance()  # consume (
                    args = []
                    while not self.check(TokenType.RIGHT_PAREN) and not self.is_at_end():
                        args.append(self.expression())
                        if not self.check(TokenType.RIGHT_PAREN):
                            self.consume(TokenType.COMMA, "Expected ',' between arguments")
                    
                    self.consume(TokenType.RIGHT_PAREN, "Expected ')' after arguments")
                    expr = MethodCall(expr, member, args)
                else:
                    expr = MemberAccess(expr, member)
                    
            elif self.match(TokenType.ARROW):
                # Pointer access
                member = self.consume(TokenType.IDENTIFIER, "Expected member name").value
                expr = PointerAccess(expr, member)
                
            elif self.match(TokenType.INCREMENT, TokenType.DECREMENT):
                # Postfix increment/decrement
                operator = self.previous().value
                expr = UnaryOp(operator, expr, prefix=False)
                
            else:
                break
        
        return expr
    
    def primary(self) -> Expression:
        """Parse primary expressions"""
        # Literals
        if self.match(TokenType.NUMBER):
            value = self.previous().value
            # Parse numeric literal
            if '.' in value or 'e' in value.lower():
                return Literal(float(value))
            else:
                return Literal(int(value, 0))  # Support different bases
        
        if self.match(TokenType.STRING):
            return Literal(self.previous().value)
        
        if self.match(TokenType.BOOLEAN):
            return Literal(self.previous().value == "True")
        
        if self.match(TokenType.NULL):
            return Literal(None)
        
        # Identifiers
        if self.match(TokenType.IDENTIFIER):
            return Identifier(self.previous().value)
        
        # Parenthesized expressions
        if self.match(TokenType.LEFT_PAREN):
            expr = self.expression()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after expression")
            return expr
        
        # List literals
        if self.match(TokenType.LEFT_BRACKET):
            elements = []
            while not self.check(TokenType.RIGHT_BRACKET) and not self.is_at_end():
                elements.append(self.expression())
                if not self.check(TokenType.RIGHT_BRACKET):
                    self.consume(TokenType.COMMA, "Expected ',' between list elements")
            
            self.consume(TokenType.RIGHT_BRACKET, "Expected ']' after list elements")
            return ListLiteral(elements)
        
        # Dictionary literals
        if self.match(TokenType.LEFT_BRACE):
            pairs = []
            while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
                key = self.expression()
                self.consume(TokenType.COLON, "Expected ':' after dictionary key")
                value = self.expression()
                pairs.append((key, value))
                
                if not self.check(TokenType.RIGHT_BRACE):
                    self.consume(TokenType.COMMA, "Expected ',' between dictionary pairs")
            
            self.consume(TokenType.RIGHT_BRACE, "Expected '}' after dictionary pairs")
            return DictLiteral(pairs)
        
        # Lambda expressions
        if self.match(TokenType.LAMBDA):
            return self.lambda_expression()
        
        # Memory allocation
        if self.match(TokenType.NEW):
            return self.new_expression()
        
        # Move expressions
        if self.match(TokenType.MOVE):
            self.consume(TokenType.LEFT_PAREN, "Expected '(' after 'move'")
            expr = self.expression()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after move expression")
            return MoveExpression(expr)
        
        # Type casting
        if self.check_cast():
            return self.cast_expression()
        
        self.error("Expected expression")
    
    def lambda_expression(self) -> Lambda:
        """Parse lambda expressions"""
        # Parameter list
        parameters = []
        if not self.check(TokenType.COLON):
            while True:
                param_name = self.consume(TokenType.IDENTIFIER, "Expected parameter name").value
                type_annotation = None
                if self.match(TokenType.COLON):
                    type_annotation = self.type_annotation()
                
                parameters.append(Parameter(param_name, type_annotation))
                
                if not self.match(TokenType.COMMA):
                    break
        
        self.consume(TokenType.COLON, "Expected ':' after lambda parameters")
        
        # Body (single expression)
        body = self.expression()
        return Lambda(parameters, body)
    
    def new_expression(self) -> NewExpression:
        """Parse new expressions"""
        type_annotation = self.type_annotation()
        
        # Constructor arguments
        arguments = []
        if self.match(TokenType.LEFT_PAREN):
            while not self.check(TokenType.RIGHT_PAREN) and not self.is_at_end():
                arguments.append(self.expression())
                if not self.check(TokenType.RIGHT_PAREN):
                    self.consume(TokenType.COMMA, "Expected ',' between arguments")
            
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after arguments")
        
        # Array allocation
        array_size = None
        if self.match(TokenType.LEFT_BRACKET):
            array_size = self.expression()
            self.consume(TokenType.RIGHT_BRACKET, "Expected ']' after array size")
        
        return NewExpression(type_annotation, arguments, array_size)
    
    def check_cast(self) -> bool:
        """Check if current position is a cast expression"""
        # Look for static_cast<type>(expr) pattern
        if self.check(TokenType.IDENTIFIER):
            identifier = self.peek().value
            if identifier in ['static_cast', 'dynamic_cast', 'reinterpret_cast', 'const_cast']:
                return True
        return False
    
    def cast_expression(self) -> Cast:
        """Parse cast expressions"""
        cast_type = self.consume(TokenType.IDENTIFIER, "Expected cast type").value
        self.consume(TokenType.LESS_THAN, "Expected '<' after cast type")
        target_type = self.type_annotation()
        self.consume(TokenType.GREATER_THAN, "Expected '>' after target type")
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after cast")
        expression = self.expression()
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after cast expression")
        
        return Cast(target_type, expression, cast_type)
    
    def type_annotation(self) -> TypeAnnotation:
        """Parse type annotations"""
        # Handle const/volatile qualifiers
        is_const = self.match(TokenType.CONST)
        is_volatile = self.match(TokenType.VOLATILE)
        
        # Base type name
        type_name = self.consume(TokenType.IDENTIFIER, "Expected type name").value
        
        # Template arguments
        template_args = []
        if self.match(TokenType.LESS_THAN):
            while not self.check(TokenType.GREATER_THAN) and not self.is_at_end():
                template_args.append(self.type_annotation())
                if not self.check(TokenType.GREATER_THAN):
                    self.consume(TokenType.COMMA, "Expected ',' between template arguments")
            
            self.consume(TokenType.GREATER_THAN, "Expected '>' after template arguments")
        
        # Pointer/reference indicators
        is_pointer = self.match(TokenType.MULTIPLY)
        is_reference = self.match(TokenType.BITWISE_AND)
        
        return TypeAnnotation(type_name, template_args, is_pointer, is_reference, is_const, is_volatile) 