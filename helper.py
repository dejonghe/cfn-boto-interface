import random
import string
from datetime import date, datetime
from logger import logger

####
# The recursion and traversal was taken, and adapted slightly from nvie.com blog:
# http://nvie.com/posts/modifying-deeply-nested-structures/
######
def traverse(obj, path=None, callback=None):
    """
    Traverse an arbitrary Python object structure (limited to JSON data
    types), calling a callback function for every element in the structure,
    and inserting the return value of the callback as the new value.
    """
    if path is None:
        path = []

    if isinstance(obj, dict):
        value = {k: traverse(v, path + [k], callback)
                 for k, v in obj.items()}
    elif isinstance(obj, list):
        value = [traverse(elem, path + [[]], callback)
                 for elem in obj]
    else:
        value = obj

    if callback is None:
        return value
    else:
        return callback(path, value)

def traverse_modify(obj, target_path, action):
    """
    Traverses an arbitrary object structure and where the path matches,
    performs the given action on the value, replacing the node with the
    action's return value.
    """
    target_path = to_path(target_path)

    def transformer(path, value):
        logger.debug("Transformer: Path: {}".format(path))
        logger.debug("Transformer: Path: Type: {}".format(type(path)))
        logger.debug("Transformer: Target Path: {}".format(target_path))
        logger.debug("Transformer: Target Path: Type: {}".format(type(target_path)))
        logger.debug("Transformer: Value: {}".format(value))
        logger.debug("Transformer: Value: Type: {}".format(type(value)))
        if path == target_path:
            return action(value)
        else:
            return value

    return traverse(obj, callback=transformer)

def traverse_find(obj, trigger, action):
    # This will get called for every path/value in the structure
    def finder(path, value):
        if isinstance(value,str):
            if value.startswith(trigger):
                return action(value)
        return value
    return traverse(obj, callback=finder)



def to_path(path):
    """
    Helper function, converting path strings into path lists.
        >>> to_path('foo')
        ['foo']
        >>> to_path('foo.bar')
        ['foo', 'bar']
        >>> to_path('foo.bar[]')
        ['foo', 'bar', []]
    """
    if isinstance(path, list):
        return path  # already in list format

    def _iter_path(path):
        for parts in path.split('[]'):
            for part in parts.strip('.').split('.'):
                yield part
            yield []

    return list(_iter_path(path))[:-1]


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, None):
        return 'None'
    raise TypeError ("Type %s not serializable" % type(obj))

# Trims prefix
def remove_prefix(text, prefix):
    return text[text.startswith(prefix) and len(prefix):]

# returns the modifier and text without modifier syntax
def return_modifier(text):
    modifiers = [ 'str', 'int' ]
    for mod in modifiers:
        mod_syntax = "!{}.".format(mod)
        if mod_syntax in text:
            return (mod,text.replace(mod_syntax,''))
    return (None,text)

# Injects random alphanumeric into value where trigger is found
def inject_rand(text, trigger):
    while trigger in text:
        text = text.replace(trigger,''.join(random.choices(string.ascii_uppercase + string.digits, k=4)),1)
    return text

def convert(value, type_):
    import importlib
    try:
        # Check if it's a builtin type
        module = importlib.import_module('builtins')
        cls = getattr(module, type_)
    except AttributeError:
        # if not, separate module and class
        module, type_ = type_.rsplit(".", 1)
        module = importlib.import_module(module)
        cls = getattr(module, type_)
    return cls(value)
