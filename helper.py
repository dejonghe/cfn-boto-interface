####
# This was taken, and adapted slightly from nvie.com blog:
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
