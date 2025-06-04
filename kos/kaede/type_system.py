"""
Kaede Type System
Advanced type system supporting both static and dynamic typing with template support.
"""

from typing import Dict, List, Optional, Set, Union, Any, TYPE_CHECKING
from abc import ABC, abstractmethod
from enum import Enum
import copy

if TYPE_CHECKING:
    from .ast_nodes import ASTNode

class TypeKind(Enum):
    """Enumeration of all type kinds in Kaede."""
    VOID = "void"
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    CHAR = "char"
    ARRAY = "array"
    LIST = "list"
    DICT = "dict"
    TUPLE = "tuple"
    SET = "set"
    FUNCTION = "function"
    CLASS = "class"
    STRUCT = "struct"
    ENUM = "enum"
    POINTER = "pointer"
    REFERENCE = "reference"
    SMART_POINTER = "smart_pointer"
    TEMPLATE = "template"
    GENERIC = "generic"
    UNION = "union"
    OPTIONAL = "optional"
    TRAIT = "trait"
    ANY = "any"
    UNKNOWN = "unknown"

class StorageClass(Enum):
    """Storage class specifiers."""
    AUTO = "auto"
    STATIC = "static"
    EXTERN = "extern"
    REGISTER = "register"
    MUTABLE = "mutable"
    THREAD_LOCAL = "thread_local"

class AccessLevel(Enum):
    """Access level modifiers."""
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"

class TypeQualifier(Enum):
    """Type qualifiers."""
    CONST = "const"
    VOLATILE = "volatile"
    RESTRICT = "restrict"
    ATOMIC = "atomic"

class SmartPointerKind(Enum):
    """Smart pointer types."""
    UNIQUE = "unique"
    SHARED = "shared"
    WEAK = "weak"
    OWNED = "owned"

class Type(ABC):
    """Base class for all types in Kaede."""
    
    def __init__(self, name: str, kind: TypeKind, qualifiers: Optional[Set[TypeQualifier]] = None):
        self.name = name
        self.kind = kind
        self.qualifiers = qualifiers or set()
        self.size = 0  # Size in bytes
        self.alignment = 1  # Alignment requirement
    
    @abstractmethod
    def is_compatible_with(self, other: 'Type') -> bool:
        """Check if this type is compatible with another type."""
        pass
    
    @abstractmethod
    def can_cast_to(self, other: 'Type') -> bool:
        """Check if this type can be cast to another type."""
        pass
    
    def is_const(self) -> bool:
        """Check if this type is const-qualified."""
        return TypeQualifier.CONST in self.qualifiers
    
    def is_volatile(self) -> bool:
        """Check if this type is volatile-qualified."""
        return TypeQualifier.VOLATILE in self.qualifiers
    
    def add_qualifier(self, qualifier: TypeQualifier) -> 'Type':
        """Add a type qualifier and return a new type."""
        new_type = copy.deepcopy(self)
        new_type.qualifiers.add(qualifier)
        return new_type
    
    def remove_qualifier(self, qualifier: TypeQualifier) -> 'Type':
        """Remove a type qualifier and return a new type."""
        new_type = copy.deepcopy(self)
        new_type.qualifiers.discard(qualifier)
        return new_type
    
    def __str__(self) -> str:
        qualifiers_str = " ".join(q.value for q in self.qualifiers)
        return f"{qualifiers_str} {self.name}".strip()
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Type):
            return False
        return (self.name == other.name and 
                self.kind == other.kind and 
                self.qualifiers == other.qualifiers)
    
    def __hash__(self) -> int:
        return hash((self.name, self.kind, frozenset(self.qualifiers)))

class PrimitiveType(Type):
    """Primitive types like int, float, bool, etc."""
    
    def __init__(self, kind: TypeKind, qualifiers: Optional[Set[TypeQualifier]] = None):
        name = kind.value
        super().__init__(name, kind, qualifiers)
        
        # Set size and alignment based on type
        size_map = {
            TypeKind.VOID: 0,
            TypeKind.BOOL: 1,
            TypeKind.CHAR: 1,
            TypeKind.INT: 8,  # 64-bit int
            TypeKind.FLOAT: 8,  # 64-bit float
            TypeKind.STRING: 8,  # Pointer size
        }
        self.size = size_map.get(kind, 8)
        self.alignment = min(self.size, 8) if self.size > 0 else 1
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, PrimitiveType):
            return self.kind == other.kind
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        if isinstance(other, PrimitiveType):
            # Numeric types can be cast to each other
            numeric_types = {TypeKind.INT, TypeKind.FLOAT, TypeKind.CHAR}
            if self.kind in numeric_types and other.kind in numeric_types:
                return True
            # Bool can be cast to numeric types
            if self.kind == TypeKind.BOOL and other.kind in numeric_types:
                return True
            # Same type casting
            return self.kind == other.kind
        return False

class ArrayType(Type):
    """Array types with fixed size."""
    
    def __init__(self, element_type: Type, size: int, qualifiers: Optional[Set[TypeQualifier]] = None):
        self.element_type = element_type
        self.array_size = size
        name = f"{element_type.name}[{size}]"
        super().__init__(name, TypeKind.ARRAY, qualifiers)
        self.size = element_type.size * size
        self.alignment = element_type.alignment
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, ArrayType):
            return (self.element_type.is_compatible_with(other.element_type) and
                    self.array_size == other.array_size)
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        if isinstance(other, ArrayType):
            return self.element_type.can_cast_to(other.element_type)
        if isinstance(other, PointerType):
            return self.element_type.is_compatible_with(other.pointed_type)
        return False

class ListType(Type):
    """Dynamic list types (Python-style)."""
    
    def __init__(self, element_type: Type, qualifiers: Optional[Set[TypeQualifier]] = None):
        self.element_type = element_type
        name = f"list[{element_type.name}]"
        super().__init__(name, TypeKind.LIST, qualifiers)
        self.size = 24  # Typical list header size
        self.alignment = 8
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, ListType):
            return self.element_type.is_compatible_with(other.element_type)
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        if isinstance(other, ListType):
            return self.element_type.can_cast_to(other.element_type)
        if isinstance(other, ArrayType):
            return self.element_type.can_cast_to(other.element_type)
        return False

class DictType(Type):
    """Dictionary types."""
    
    def __init__(self, key_type: Type, value_type: Type, qualifiers: Optional[Set[TypeQualifier]] = None):
        self.key_type = key_type
        self.value_type = value_type
        name = f"dict[{key_type.name}, {value_type.name}]"
        super().__init__(name, TypeKind.DICT, qualifiers)
        self.size = 48  # Typical dict header size
        self.alignment = 8
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, DictType):
            return (self.key_type.is_compatible_with(other.key_type) and
                    self.value_type.is_compatible_with(other.value_type))
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        if isinstance(other, DictType):
            return (self.key_type.can_cast_to(other.key_type) and
                    self.value_type.can_cast_to(other.value_type))
        return False

class TupleType(Type):
    """Tuple types with fixed elements."""
    
    def __init__(self, element_types: List[Type], qualifiers: Optional[Set[TypeQualifier]] = None):
        self.element_types = element_types
        type_names = ", ".join(t.name for t in element_types)
        name = f"({type_names})"
        super().__init__(name, TypeKind.TUPLE, qualifiers)
        self.size = sum(t.size for t in element_types)
        self.alignment = max((t.alignment for t in element_types), default=1)
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, TupleType):
            if len(self.element_types) != len(other.element_types):
                return False
            return all(a.is_compatible_with(b) for a, b in 
                      zip(self.element_types, other.element_types))
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        if isinstance(other, TupleType):
            if len(self.element_types) != len(other.element_types):
                return False
            return all(a.can_cast_to(b) for a, b in 
                      zip(self.element_types, other.element_types))
        return False

class PointerType(Type):
    """Pointer types."""
    
    def __init__(self, pointed_type: Type, qualifiers: Optional[Set[TypeQualifier]] = None):
        self.pointed_type = pointed_type
        name = f"{pointed_type.name}*"
        super().__init__(name, TypeKind.POINTER, qualifiers)
        self.size = 8  # 64-bit pointer
        self.alignment = 8
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, PointerType):
            return self.pointed_type.is_compatible_with(other.pointed_type)
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        if isinstance(other, PointerType):
            return True  # All pointers can be cast to each other
        if other.kind == TypeKind.INT:
            return True  # Pointers can be cast to integers
        return False

class ReferenceType(Type):
    """Reference types (C++ style)."""
    
    def __init__(self, referenced_type: Type, qualifiers: Optional[Set[TypeQualifier]] = None):
        self.referenced_type = referenced_type
        name = f"{referenced_type.name}&"
        super().__init__(name, TypeKind.REFERENCE, qualifiers)
        self.size = referenced_type.size
        self.alignment = referenced_type.alignment
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, ReferenceType):
            return self.referenced_type.is_compatible_with(other.referenced_type)
        return self.referenced_type.is_compatible_with(other)
    
    def can_cast_to(self, other: Type) -> bool:
        return self.referenced_type.can_cast_to(other)

class SmartPointerType(Type):
    """Smart pointer types (unique_ptr, shared_ptr, etc.)."""
    
    def __init__(self, pointed_type: Type, kind: SmartPointerKind, 
                 qualifiers: Optional[Set[TypeQualifier]] = None):
        self.pointed_type = pointed_type
        self.smart_kind = kind
        name = f"{kind.value}<{pointed_type.name}>"
        super().__init__(name, TypeKind.SMART_POINTER, qualifiers)
        self.size = 16 if kind == SmartPointerKind.SHARED else 8
        self.alignment = 8
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, SmartPointerType):
            return (self.smart_kind == other.smart_kind and
                    self.pointed_type.is_compatible_with(other.pointed_type))
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        if isinstance(other, SmartPointerType):
            # Can cast between compatible smart pointer types
            return self.pointed_type.can_cast_to(other.pointed_type)
        if isinstance(other, PointerType):
            return self.pointed_type.is_compatible_with(other.pointed_type)
        return False

class FunctionType(Type):
    """Function types with parameters and return type."""
    
    def __init__(self, return_type: Type, parameter_types: List[Type], 
                 is_async: bool = False, qualifiers: Optional[Set[TypeQualifier]] = None):
        self.return_type = return_type
        self.parameter_types = parameter_types
        self.is_async = is_async
        
        param_names = ", ".join(t.name for t in parameter_types)
        async_prefix = "async " if is_async else ""
        name = f"{async_prefix}({param_names}) -> {return_type.name}"
        super().__init__(name, TypeKind.FUNCTION, qualifiers)
        self.size = 8  # Function pointer size
        self.alignment = 8
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, FunctionType):
            if (self.is_async != other.is_async or
                len(self.parameter_types) != len(other.parameter_types)):
                return False
            
            if not self.return_type.is_compatible_with(other.return_type):
                return False
            
            return all(a.is_compatible_with(b) for a, b in 
                      zip(self.parameter_types, other.parameter_types))
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        return self.is_compatible_with(other)

class ClassType(Type):
    """Class types with inheritance and members."""
    
    def __init__(self, name: str, fields: Optional[Dict[str, Type]] = None,
                 methods: Optional[Dict[str, FunctionType]] = None,
                 base_classes: Optional[List['ClassType']] = None,
                 access_level: AccessLevel = AccessLevel.PUBLIC,
                 qualifiers: Optional[Set[TypeQualifier]] = None):
        super().__init__(name, TypeKind.CLASS, qualifiers)
        self.fields = fields or {}
        self.methods = methods or {}
        self.base_classes = base_classes or []
        self.access_level = access_level
        self.is_abstract = False
        self.size = self._calculate_size()
        self.alignment = 8
    
    def _calculate_size(self) -> int:
        """Calculate the size of the class including fields and vtable."""
        size = 8  # Base size for vtable pointer
        for field_type in self.fields.values():
            size += field_type.size
        return size
    
    def add_field(self, name: str, field_type: Type) -> None:
        """Add a field to the class."""
        self.fields[name] = field_type
        self.size = self._calculate_size()
    
    def add_method(self, name: str, method_type: FunctionType) -> None:
        """Add a method to the class."""
        self.methods[name] = method_type
    
    def has_field(self, name: str) -> bool:
        """Check if class has a field with given name."""
        if name in self.fields:
            return True
        return any(base.has_field(name) for base in self.base_classes)
    
    def has_method(self, name: str) -> bool:
        """Check if class has a method with given name."""
        if name in self.methods:
            return True
        return any(base.has_method(name) for base in self.base_classes)
    
    def is_derived_from(self, other: 'ClassType') -> bool:
        """Check if this class is derived from another class."""
        if self == other:
            return True
        return any(base.is_derived_from(other) for base in self.base_classes)
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, ClassType):
            return self == other or self.is_derived_from(other)
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        if isinstance(other, ClassType):
            return self.is_derived_from(other) or other.is_derived_from(self)
        return False

class StructType(ClassType):
    """Struct types (similar to classes but with public default access)."""
    
    def __init__(self, name: str, fields: Optional[Dict[str, Type]] = None,
                 qualifiers: Optional[Set[TypeQualifier]] = None):
        super().__init__(name, fields, {}, [], AccessLevel.PUBLIC, qualifiers)
        self.kind = TypeKind.STRUCT

class EnumType(Type):
    """Enumeration types."""
    
    def __init__(self, name: str, values: Dict[str, int], 
                 underlying_type: Type = None,
                 qualifiers: Optional[Set[TypeQualifier]] = None):
        super().__init__(name, TypeKind.ENUM, qualifiers)
        self.values = values
        self.underlying_type = underlying_type or PrimitiveType(TypeKind.INT)
        self.size = self.underlying_type.size
        self.alignment = self.underlying_type.alignment
    
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, EnumType):
            return self.name == other.name
        return False
    
    def can_cast_to(self, other: Type) -> bool:
        if isinstance(other, EnumType):
            return self.name == other.name
        return self.underlying_type.can_cast_to(other)

class TemplateType(Type):
    """Template types with type parameters."""
    
    def __init__(self, name: str, type_parameters: List[str],
                 qualifiers: Optional[Set[TypeQualifier]] = None):
        super().__init__(name, TypeKind.TEMPLATE, qualifiers)
        self.type_parameters = type_parameters
        self.specializations: Dict[tuple, Type] = {}
    
    def instantiate(self, type_arguments: List[Type]) -> Type:
        """Instantiate the template with concrete types."""
        if len(type_arguments) != len(self.type_parameters):
            raise ValueError(f"Wrong number of type arguments for {self.name}")
        
        key = tuple(type_arguments)
        if key not in self.specializations:
            # Create a new specialized type
            # This would involve actual template instantiation logic
            pass
        
        return self.specializations.get(key)
    
    def is_compatible_with(self, other: Type) -> bool:
        return isinstance(other, TemplateType) and self.name == other.name
    
    def can_cast_to(self, other: Type) -> bool:
        return self.is_compatible_with(other)

class TypeSystem:
    """Central type system managing all types and type checking."""
    
    def __init__(self):
        self.types: Dict[str, Type] = {}
        self.template_types: Dict[str, TemplateType] = {}
        self._init_builtin_types()
    
    def _init_builtin_types(self) -> None:
        """Initialize builtin types."""
        # Primitive types
        self.void_type = PrimitiveType(TypeKind.VOID)
        self.bool_type = PrimitiveType(TypeKind.BOOL)
        self.int_type = PrimitiveType(TypeKind.INT)
        self.float_type = PrimitiveType(TypeKind.FLOAT)
        self.string_type = PrimitiveType(TypeKind.STRING)
        self.char_type = PrimitiveType(TypeKind.CHAR)
        
        # Register builtin types
        self.types.update({
            "void": self.void_type,
            "bool": self.bool_type,
            "int": self.int_type,
            "float": self.float_type,
            "string": self.string_type,
            "char": self.char_type,
        })
    
    def register_type(self, type_obj: Type) -> None:
        """Register a new type in the system."""
        self.types[type_obj.name] = type_obj
    
    def get_type(self, name: str) -> Optional[Type]:
        """Get a type by name."""
        return self.types.get(name)
    
    def create_array_type(self, element_type: Type, size: int) -> ArrayType:
        """Create an array type."""
        return ArrayType(element_type, size)
    
    def create_list_type(self, element_type: Type) -> ListType:
        """Create a list type."""
        return ListType(element_type)
    
    def create_dict_type(self, key_type: Type, value_type: Type) -> DictType:
        """Create a dictionary type."""
        return DictType(key_type, value_type)
    
    def create_pointer_type(self, pointed_type: Type) -> PointerType:
        """Create a pointer type."""
        return PointerType(pointed_type)
    
    def create_reference_type(self, referenced_type: Type) -> ReferenceType:
        """Create a reference type."""
        return ReferenceType(referenced_type)
    
    def create_function_type(self, return_type: Type, parameter_types: List[Type],
                           is_async: bool = False) -> FunctionType:
        """Create a function type."""
        return FunctionType(return_type, parameter_types, is_async)
    
    def is_assignable(self, from_type: Type, to_type: Type) -> bool:
        """Check if a value of from_type can be assigned to to_type."""
        return from_type.is_compatible_with(to_type) or from_type.can_cast_to(to_type)
    
    def find_common_type(self, type1: Type, type2: Type) -> Optional[Type]:
        """Find the common type for two types (for type inference)."""
        if type1.is_compatible_with(type2):
            return type2
        if type2.is_compatible_with(type1):
            return type1
        
        # Check for numeric promotions
        if (isinstance(type1, PrimitiveType) and isinstance(type2, PrimitiveType)):
            if type1.kind == TypeKind.FLOAT or type2.kind == TypeKind.FLOAT:
                return self.float_type
            if type1.kind == TypeKind.INT or type2.kind == TypeKind.INT:
                return self.int_type
        
        return None
    
    def get_member_type(self, base_type: Type, member_name: str) -> Optional[Type]:
        """Get the type of a member from a class/struct type."""
        if isinstance(base_type, (ClassType, StructType)):
            if member_name in base_type.fields:
                return base_type.fields[member_name]
            if member_name in base_type.methods:
                return base_type.methods[member_name]
            
            # Check base classes
            for base_class in base_type.base_classes:
                member_type = self.get_member_type(base_class, member_name)
                if member_type:
                    return member_type
        
        return None
    
    def resolve_function_overload(self, function_name: str, argument_types: List[Type],
                                available_overloads: List[FunctionType]) -> Optional[FunctionType]:
        """Resolve function overload based on argument types."""
        exact_matches = []
        compatible_matches = []
        
        for overload in available_overloads:
            if len(overload.parameter_types) != len(argument_types):
                continue
            
            is_exact = True
            is_compatible = True
            
            for arg_type, param_type in zip(argument_types, overload.parameter_types):
                if not arg_type.is_compatible_with(param_type):
                    is_exact = False
                    if not arg_type.can_cast_to(param_type):
                        is_compatible = False
                        break
            
            if is_compatible:
                if is_exact:
                    exact_matches.append(overload)
                else:
                    compatible_matches.append(overload)
        
        # Prefer exact matches
        if exact_matches:
            return exact_matches[0]  # Return first exact match
        if compatible_matches:
            return compatible_matches[0]  # Return first compatible match
        
        return None 