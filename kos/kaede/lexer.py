"""
Kaede Language Lexer
===================

Tokenizes Kaede source code supporting:
- Python-like syntax (indentation, colons, etc.)
- C++-like syntax (braces, semicolons, templates)
- Hybrid type annotations
- Memory management operators
- Modern language features
"""

import re
import enum
from dataclasses import dataclass
from typing import List, Optional, Iterator, NamedTuple
from .exceptions import KaedeSyntaxError

class TokenType(enum.Enum):
    # Literals
    NUMBER = "NUMBER"
    STRING = "STRING" 
    BOOLEAN = "BOOLEAN"
    NULL = "NULL"
    
    # Identifiers and keywords
    IDENTIFIER = "IDENTIFIER"
    
    # Python-style keywords
    IF = "if"
    ELIF = "elif"
    ELSE = "else"
    FOR = "for"
    WHILE = "while"
    DEF = "def"
    CLASS = "class"
    RETURN = "return"
    BREAK = "break"
    CONTINUE = "continue"
    PASS = "pass"
    IN = "in"
    IS = "is"
    NOT = "not"
    AND = "and"
    OR = "or"
    IMPORT = "import"
    FROM = "from"
    AS = "as"
    TRY = "try"
    EXCEPT = "except"
    FINALLY = "finally"
    RAISE = "raise"
    WITH = "with"
    YIELD = "yield"
    ASYNC = "async"
    AWAIT = "await"
    LAMBDA = "lambda"
    GLOBAL = "global"
    NONLOCAL = "nonlocal"
    
    # C++-style keywords
    TEMPLATE = "template"
    TYPENAME = "typename"
    NAMESPACE = "namespace"
    USING = "using"
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    STATIC = "static"
    CONST = "const"
    VIRTUAL = "virtual"
    OVERRIDE = "override"
    FINAL = "final"
    EXPLICIT = "explicit"
    INLINE = "inline"
    FRIEND = "friend"
    OPERATOR = "operator"
    SIZEOF = "sizeof"
    TYPEOF = "typeof"
    AUTO = "auto"
    
    # Kaede-specific keywords
    LET = "let"
    VAR = "var"
    MUT = "mut"
    REF = "ref"
    PTR = "ptr"
    OWNED = "owned"
    SHARED = "shared"
    WEAK = "weak"
    UNIQUE = "unique"
    MOVE = "move"
    COPY = "copy"
    CLONE = "clone"
    UNSAFE = "unsafe"
    MATCH = "match"
    WHEN = "when"
    WHERE = "where"
    IMPL = "impl"
    TRAIT = "trait"
    ENUM = "enum"
    STRUCT = "struct"
    UNION = "union"
    
    # Memory management
    NEW = "new"
    DELETE = "delete"
    MALLOC = "malloc"
    FREE = "free"
    GARBAGE_COLLECT = "gc"
    
    # Type keywords
    INT = "int"
    FLOAT = "float"
    DOUBLE = "double"
    CHAR = "char"
    BOOL = "bool"
    VOID = "void"
    STRING_TYPE = "string"
    BYTES = "bytes"
    LIST = "list"
    DICT = "dict"
    SET = "set"
    TUPLE = "tuple"
    
    # Operators
    PLUS = "+"
    MINUS = "-"
    MULTIPLY = "*"
    DIVIDE = "/"
    MODULO = "%"
    POWER = "**"
    FLOOR_DIVIDE = "//"
    
    # Assignment operators
    ASSIGN = "="
    PLUS_ASSIGN = "+="
    MINUS_ASSIGN = "-="
    MULTIPLY_ASSIGN = "*="
    DIVIDE_ASSIGN = "/="
    MODULO_ASSIGN = "%="
    POWER_ASSIGN = "**="
    FLOOR_DIVIDE_ASSIGN = "//="
    BITWISE_AND_ASSIGN = "&="
    BITWISE_OR_ASSIGN = "|="
    BITWISE_XOR_ASSIGN = "^="
    LEFT_SHIFT_ASSIGN = "<<="
    RIGHT_SHIFT_ASSIGN = ">>="
    
    # Comparison operators
    EQUAL = "=="
    NOT_EQUAL = "!="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_EQUAL = "<="
    GREATER_EQUAL = ">="
    SPACESHIP = "<=>"  # C++20 three-way comparison
    
    # Bitwise operators
    BITWISE_AND = "&"
    BITWISE_OR = "|"
    BITWISE_XOR = "^"
    BITWISE_NOT = "~"
    LEFT_SHIFT = "<<"
    RIGHT_SHIFT = ">>"
    
    # Logical operators
    LOGICAL_AND = "&&"
    LOGICAL_OR = "||"
    LOGICAL_NOT = "!"
    
    # Unary operators
    INCREMENT = "++"
    DECREMENT = "--"
    
    # Pointer operators
    DEREFERENCE = "*"
    ADDRESS_OF = "&"
    ARROW = "->"
    DOT = "."
    SCOPE_RESOLUTION = "::"
    
    # Delimiters
    SEMICOLON = ";"
    COLON = ":"
    COMMA = ","
    QUESTION = "?"
    HASH = "#"
    AT = "@"
    DOLLAR = "$"
    
    # Brackets
    LEFT_PAREN = "("
    RIGHT_PAREN = ")"
    LEFT_BRACKET = "["
    RIGHT_BRACKET = "]"
    LEFT_BRACE = "{"
    RIGHT_BRACE = "}"
    LEFT_ANGLE = "<"
    RIGHT_ANGLE = ">"
    
    # Special
    NEWLINE = "NEWLINE"
    INDENT = "INDENT"
    DEDENT = "DEDENT"
    EOF = "EOF"
    
    # Comments
    COMMENT = "COMMENT"
    MULTILINE_COMMENT = "MULTILINE_COMMENT"

@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    position: int

class KaedeLexer:
    """Lexical analyzer for Kaede language"""
    
    # Keywords mapping
    KEYWORDS = {
        # Python-style
        'if': TokenType.IF, 'elif': TokenType.ELIF, 'else': TokenType.ELSE,
        'for': TokenType.FOR, 'while': TokenType.WHILE, 'def': TokenType.DEF,
        'class': TokenType.CLASS, 'return': TokenType.RETURN, 'break': TokenType.BREAK,
        'continue': TokenType.CONTINUE, 'pass': TokenType.PASS, 'in': TokenType.IN,
        'is': TokenType.IS, 'not': TokenType.NOT, 'and': TokenType.AND, 'or': TokenType.OR,
        'import': TokenType.IMPORT, 'from': TokenType.FROM, 'as': TokenType.AS,
        'try': TokenType.TRY, 'except': TokenType.EXCEPT, 'finally': TokenType.FINALLY,
        'raise': TokenType.RAISE, 'with': TokenType.WITH, 'yield': TokenType.YIELD,
        'async': TokenType.ASYNC, 'await': TokenType.AWAIT, 'lambda': TokenType.LAMBDA,
        'global': TokenType.GLOBAL, 'nonlocal': TokenType.NONLOCAL,
        
        # C++-style
        'template': TokenType.TEMPLATE, 'typename': TokenType.TYPENAME,
        'namespace': TokenType.NAMESPACE, 'using': TokenType.USING,
        'public': TokenType.PUBLIC, 'private': TokenType.PRIVATE,
        'protected': TokenType.PROTECTED, 'static': TokenType.STATIC,
        'const': TokenType.CONST, 'virtual': TokenType.VIRTUAL,
        'override': TokenType.OVERRIDE, 'final': TokenType.FINAL,
        'explicit': TokenType.EXPLICIT, 'inline': TokenType.INLINE,
        'friend': TokenType.FRIEND, 'operator': TokenType.OPERATOR,
        'sizeof': TokenType.SIZEOF, 'typeof': TokenType.TYPEOF, 'auto': TokenType.AUTO,
        
        # Kaede-specific
        'let': TokenType.LET, 'var': TokenType.VAR, 'mut': TokenType.MUT,
        'ref': TokenType.REF, 'ptr': TokenType.PTR, 'owned': TokenType.OWNED,
        'shared': TokenType.SHARED, 'weak': TokenType.WEAK, 'unique': TokenType.UNIQUE,
        'move': TokenType.MOVE, 'copy': TokenType.COPY, 'clone': TokenType.CLONE,
        'unsafe': TokenType.UNSAFE, 'match': TokenType.MATCH, 'when': TokenType.WHEN,
        'where': TokenType.WHERE, 'impl': TokenType.IMPL, 'trait': TokenType.TRAIT,
        'enum': TokenType.ENUM, 'struct': TokenType.STRUCT, 'union': TokenType.UNION,
        
        # Memory management
        'new': TokenType.NEW, 'delete': TokenType.DELETE, 'malloc': TokenType.MALLOC,
        'free': TokenType.FREE, 'gc': TokenType.GARBAGE_COLLECT,
        
        # Types
        'int': TokenType.INT, 'float': TokenType.FLOAT, 'double': TokenType.DOUBLE,
        'char': TokenType.CHAR, 'bool': TokenType.BOOL, 'void': TokenType.VOID,
        'string': TokenType.STRING_TYPE, 'bytes': TokenType.BYTES,
        'list': TokenType.LIST, 'dict': TokenType.DICT, 'set': TokenType.SET,
        'tuple': TokenType.TUPLE,
        
        # Literals
        'True': TokenType.BOOLEAN, 'False': TokenType.BOOLEAN,
        'None': TokenType.NULL, 'null': TokenType.NULL, 'nullptr': TokenType.NULL,
    }
    
    def __init__(self):
        self.text = ""
        self.position = 0
        self.line = 1
        self.column = 1
        self.indent_stack = [0]
        self.tokens = []
        
    def error(self, message: str) -> None:
        """Raise a syntax error with current position"""
        raise KaedeSyntaxError(f"Line {self.line}, Col {self.column}: {message}")
        
    def current_char(self) -> Optional[str]:
        """Get current character"""
        if self.position >= len(self.text):
            return None
        return self.text[self.position]
        
    def peek_char(self, offset: int = 1) -> Optional[str]:
        """Peek at character ahead"""
        pos = self.position + offset
        if pos >= len(self.text):
            return None
        return self.text[pos]
        
    def advance(self) -> None:
        """Move to next character"""
        if self.position < len(self.text) and self.text[self.position] == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.position += 1
        
    def skip_whitespace(self) -> None:
        """Skip whitespace except newlines"""
        while self.current_char() and self.current_char() in ' \t\r':
            self.advance()
            
    def read_number(self) -> Token:
        """Read numeric literal"""
        start_pos = self.position
        start_col = self.column
        value = ""
        
        # Handle binary, octal, hex
        if self.current_char() == '0':
            value += self.current_char()
            self.advance()
            if self.current_char() in 'bB':
                value += self.current_char()
                self.advance()
                while self.current_char() and self.current_char() in '01_':
                    if self.current_char() != '_':
                        value += self.current_char()
                    self.advance()
            elif self.current_char() in 'oO':
                value += self.current_char()
                self.advance()
                while self.current_char() and self.current_char() in '01234567_':
                    if self.current_char() != '_':
                        value += self.current_char()
                    self.advance()
            elif self.current_char() in 'xX':
                value += self.current_char()
                self.advance()
                while self.current_char() and self.current_char() in '0123456789abcdefABCDEF_':
                    if self.current_char() != '_':
                        value += self.current_char()
                    self.advance()
        else:
            # Decimal number
            while self.current_char() and (self.current_char().isdigit() or self.current_char() == '_'):
                if self.current_char() != '_':
                    value += self.current_char()
                self.advance()
                
        # Handle decimal point
        if self.current_char() == '.' and self.peek_char() and self.peek_char().isdigit():
            value += self.current_char()
            self.advance()
            while self.current_char() and (self.current_char().isdigit() or self.current_char() == '_'):
                if self.current_char() != '_':
                    value += self.current_char()
                self.advance()
                
        # Handle scientific notation
        if self.current_char() and self.current_char().lower() == 'e':
            value += self.current_char()
            self.advance()
            if self.current_char() in '+-':
                value += self.current_char()
                self.advance()
            while self.current_char() and self.current_char().isdigit():
                value += self.current_char()
                self.advance()
                
        # Handle type suffixes (C++ style)
        if self.current_char() and self.current_char().lower() in 'lulf':
            value += self.current_char()
            self.advance()
            
        return Token(TokenType.NUMBER, value, self.line, start_col, start_pos)
        
    def read_string(self, quote_char: str) -> Token:
        """Read string literal"""
        start_pos = self.position
        start_col = self.column
        value = ""
        self.advance()  # Skip opening quote
        
        while self.current_char() and self.current_char() != quote_char:
            if self.current_char() == '\\':
                self.advance()
                if self.current_char() is None:
                    self.error("Unterminated string literal")
                # Handle escape sequences
                escape_map = {
                    'n': '\n', 't': '\t', 'r': '\r', 'b': '\b',
                    'f': '\f', 'v': '\v', 'a': '\a', '0': '\0',
                    '\\': '\\', "'": "'", '"': '"'
                }
                if self.current_char() in escape_map:
                    value += escape_map[self.current_char()]
                elif self.current_char() == 'x':
                    # Hex escape
                    self.advance()
                    hex_digits = ""
                    for _ in range(2):
                        if self.current_char() and self.current_char() in '0123456789abcdefABCDEF':
                            hex_digits += self.current_char()
                            self.advance()
                        else:
                            break
                    if len(hex_digits) == 2:
                        value += chr(int(hex_digits, 16))
                        continue
                    else:
                        self.error("Invalid hex escape sequence")
                elif self.current_char().isdigit():
                    # Octal escape
                    octal_digits = ""
                    for _ in range(3):
                        if self.current_char() and self.current_char() in '01234567':
                            octal_digits += self.current_char()
                            self.advance()
                        else:
                            break
                    if octal_digits:
                        value += chr(int(octal_digits, 8))
                        continue
                    else:
                        value += self.current_char()
                else:
                    value += self.current_char()
            else:
                value += self.current_char()
            self.advance()
            
        if self.current_char() != quote_char:
            self.error("Unterminated string literal")
            
        self.advance()  # Skip closing quote
        return Token(TokenType.STRING, value, self.line, start_col, start_pos)
        
    def read_identifier(self) -> Token:
        """Read identifier or keyword"""
        start_pos = self.position
        start_col = self.column
        value = ""
        
        while (self.current_char() and 
               (self.current_char().isalnum() or self.current_char() in '_$')):
            value += self.current_char()
            self.advance()
            
        token_type = self.KEYWORDS.get(value, TokenType.IDENTIFIER)
        return Token(token_type, value, self.line, start_col, start_pos)
        
    def read_comment(self) -> Optional[Token]:
        """Read single or multi-line comment"""
        start_pos = self.position
        start_col = self.column
        
        if self.current_char() == '#':
            # Python-style comment
            value = ""
            while self.current_char() and self.current_char() != '\n':
                value += self.current_char()
                self.advance()
            return Token(TokenType.COMMENT, value, self.line, start_col, start_pos)
            
        elif self.current_char() == '/' and self.peek_char() == '/':
            # C++-style comment
            value = ""
            self.advance()  # Skip first /
            self.advance()  # Skip second /
            while self.current_char() and self.current_char() != '\n':
                value += self.current_char()
                self.advance()
            return Token(TokenType.COMMENT, value, self.line, start_col, start_pos)
            
        elif self.current_char() == '/' and self.peek_char() == '*':
            # C-style multiline comment
            value = ""
            self.advance()  # Skip /
            self.advance()  # Skip *
            
            while self.current_char():
                if self.current_char() == '*' and self.peek_char() == '/':
                    self.advance()  # Skip *
                    self.advance()  # Skip /
                    break
                value += self.current_char()
                self.advance()
            else:
                self.error("Unterminated multiline comment")
                
            return Token(TokenType.MULTILINE_COMMENT, value, self.line, start_col, start_pos)
            
        return None
        
    def tokenize(self, text: str) -> List[Token]:
        """Tokenize input text"""
        self.text = text
        self.position = 0
        self.line = 1
        self.column = 1
        self.indent_stack = [0]
        self.tokens = []
        
        while self.position < len(self.text):
            # Handle indentation at start of line
            if self.column == 1 and self.current_char() in ' \t':
                indent_level = 0
                while self.current_char() in ' \t':
                    if self.current_char() == ' ':
                        indent_level += 1
                    else:  # tab
                        indent_level += 8
                    self.advance()
                    
                # Skip empty lines and comments
                if self.current_char() in '\n#' or (
                    self.current_char() == '/' and self.peek_char() in '/*'
                ):
                    continue
                    
                # Handle indentation changes
                if indent_level > self.indent_stack[-1]:
                    self.indent_stack.append(indent_level)
                    self.tokens.append(Token(TokenType.INDENT, "", self.line, 1, self.position))
                elif indent_level < self.indent_stack[-1]:
                    while self.indent_stack and indent_level < self.indent_stack[-1]:
                        self.indent_stack.pop()
                        self.tokens.append(Token(TokenType.DEDENT, "", self.line, 1, self.position))
                    if indent_level != self.indent_stack[-1]:
                        self.error("Indentation error")
                        
            self.skip_whitespace()
            
            if not self.current_char():
                break
                
            char = self.current_char()
            start_pos = self.position
            start_col = self.column
            
            # Numbers
            if char.isdigit():
                self.tokens.append(self.read_number())
                continue
                
            # Strings
            if char in '"\'':
                self.tokens.append(self.read_string(char))
                continue
                
            # Raw strings
            if char == 'r' and self.peek_char() in '"\'':
                self.advance()
                quote = self.current_char()
                self.tokens.append(self.read_string(quote))
                continue
                
            # F-strings
            if char == 'f' and self.peek_char() in '"\'':
                self.advance()
                quote = self.current_char()
                token = self.read_string(quote)
                token.type = TokenType.STRING  # Mark as f-string in AST
                self.tokens.append(token)
                continue
                
            # Identifiers and keywords
            if char.isalpha() or char in '_$':
                self.tokens.append(self.read_identifier())
                continue
                
            # Comments
            comment_token = self.read_comment()
            if comment_token:
                self.tokens.append(comment_token)
                continue
                
            # Multi-character operators
            two_char = char + (self.peek_char() or '')
            three_char = two_char + (self.peek_char(2) or '')
            
            if three_char in ['<<=', '>>=', '**=', '//=', '<=>']:
                self.tokens.append(Token(TokenType(three_char), three_char, self.line, start_col, start_pos))
                self.advance()
                self.advance()
                self.advance()
                continue
                
            if two_char in ['==', '!=', '<=', '>=', '&&', '||', '<<', '>>', '++'  '--', 
                           '->', '::', '**', '//', '+=', '-=', '*=', '/=', '%=',
                           '&=', '|=', '^=']:
                self.tokens.append(Token(TokenType(two_char), two_char, self.line, start_col, start_pos))
                self.advance()
                self.advance()
                continue
                
            # Single character tokens
            single_char_tokens = {
                '+': TokenType.PLUS, '-': TokenType.MINUS, '*': TokenType.MULTIPLY,
                '/': TokenType.DIVIDE, '%': TokenType.MODULO, '=': TokenType.ASSIGN,
                '<': TokenType.LESS_THAN, '>': TokenType.GREATER_THAN,
                '!': TokenType.LOGICAL_NOT, '&': TokenType.BITWISE_AND,
                '|': TokenType.BITWISE_OR, '^': TokenType.BITWISE_XOR,
                '~': TokenType.BITWISE_NOT, '(': TokenType.LEFT_PAREN,
                ')': TokenType.RIGHT_PAREN, '[': TokenType.LEFT_BRACKET,
                ']': TokenType.RIGHT_BRACKET, '{': TokenType.LEFT_BRACE,
                '}': TokenType.RIGHT_BRACE, ';': TokenType.SEMICOLON,
                ':': TokenType.COLON, ',': TokenType.COMMA, '.': TokenType.DOT,
                '?': TokenType.QUESTION, '#': TokenType.HASH, '@': TokenType.AT,
                '$': TokenType.DOLLAR
            }
            
            if char in single_char_tokens:
                self.tokens.append(Token(single_char_tokens[char], char, self.line, start_col, start_pos))
                self.advance()
                continue
                
            # Newlines
            if char == '\n':
                self.tokens.append(Token(TokenType.NEWLINE, char, self.line, start_col, start_pos))
                self.advance()
                continue
                
            # Unknown character
            self.error(f"Unexpected character: '{char}'")
            
        # Add remaining dedents
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(Token(TokenType.DEDENT, "", self.line, self.column, self.position))
            
        # Add EOF token
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column, self.position))
        
        return self.tokens 