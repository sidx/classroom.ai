class ConnectionError(Exception):
    """Raised when there is an error connecting to Elasticsearch"""
    pass

class SearchError(Exception):
    """Raised when there is an error performing a search operation"""
    pass
