class Stack:
    """A LIFO stack.

    Methods to implement:
        push(item)     — push item onto the top
        pop()          — remove and return the top item; raise IndexError if empty
        peek()         — return the top item without removing; raise IndexError if empty
        is_empty()     — return True if the stack has no items
        size()         — return the number of items
    """

    def push(self, item):
        raise NotImplementedError

    def pop(self):
        raise NotImplementedError

    def peek(self):
        raise NotImplementedError

    def is_empty(self):
        raise NotImplementedError

    def size(self):
        raise NotImplementedError
