# emport
Python dynamic imports and object filtering  


## Usage examples

### Import objects by class (emport_by_class)
```python
>>> import emport
# Get all the instances of MyClass (already defined) from the module 'my_module'
# module path and from_list are just as passed to __import__
>>> emport.emport_by_class("my_module", MyClass, ["*"])
```

### Set `__all__` dynamically to all modules within a dir
```python
# in your __init__.py
from emport import dynamic_all
__all__ = dynamic_all(__file__)
```

### Get caller function
```python
from emport import get_caller
def func(x):
    funcs_details = get_caller()
    funcs_caller_details = get_caller(1)
```

### Check if a class derives from a class (like isinstance, just for classes)
```python
class A (object):
    pass
    
class B (A):
    pass
        
>>> from emport import ObjectUtils       
>>> ObjectUtils.is_derived_of(B, A)
True    
```

