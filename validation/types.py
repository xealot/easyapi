"""
Define parameter types and collections to properly 
validate input of RPC calls.
"""
from ..exceptions import InvalidParameters

#This is to also accept None values.
class NoValue(object): pass

class BaseType(object):
    type_check = ()
    
    def __init__(self, required=True, default=None):
        self.required = required
        self.default = default
    
    def validate(self, keyword, value=NoValue):
        if value is NoValue:
            if self.required is True:
                raise InvalidParameters('Argument "%s" is required.' % keyword)
            value = self.default

        if value is not None and (self.type_check and not isinstance(value, self.type_check)):
            raise InvalidParameters('Argument "%s" must be a valid %s, got %s instead.' % (keyword, self.name, type(value).__name__))
        return value

class Any(BaseType):
    pass

class String(BaseType):
    name = "String"
    type_check = (basestring,)

class Integer(BaseType):
    name = "Integer"
    type_check = (int,)

class Float(BaseType):
    name = "Float"
    type_check = (float,)

class Boolean(BaseType):
    name = "Boolean"
    type_check = (bool,)

class List(BaseType):
    name = "List/Sequence"
    type_check = (list,)

class Dict(BaseType):
    name = "Hash/Dictionary"
    type_check = (dict,)


def validate_parameters(argspec, params, values):
    """
    Take the argspec, type params and passed in values and 
    validates them. 
    
    Returns a dictionary of arg -> cleaned value
    """
    cleaned = {}
    #Validate invocations parameters against descriptor params. Skip first in argspec (self)
    if argspec.args[0] == 'self':
        args = argspec.args[1:]
    else:
        args = argspec.args
    
    for arg, param in zip(args, params):
        if arg in values:
            value = param.validate(arg, values.get(arg))
        else:
            value = param.validate(arg)
        cleaned[arg] = value
    return cleaned



