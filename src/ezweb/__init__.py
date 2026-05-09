'''EZWeb is a Python web framework that allows you to create web applications with ease. It provides a simple and intuitive API for defining routes, handling requests, and rendering templates. With EZWeb, you can quickly build web applications without the need for complex configurations or boilerplate code.
'''

from .core.app import PageRoute, App
from .core.page import Page

__all__ = ["PageRoute", "App", "Page"]
