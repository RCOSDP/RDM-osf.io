class FileException(Exception):
    pass


class SubclassNotFound(FileException):
    pass


class VersionNotFoundError(FileException):
    pass


class FileNodeCheckedOutError(FileException):
    """
    This is to be raised if a fileNode (file or folder) is checked
    out, or if any of its children is checked out
    """
    pass

class FileNodeLockedError(FileException):
    """
    This is to be raised if a fileNode (file or folder) is locked
    """
    pass


class FileNodeIsPrimaryFile(FileException):
    pass
