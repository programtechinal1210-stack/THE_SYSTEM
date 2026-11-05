class BaseException(Exception):
    def __init__(self, message: str, code: str = "ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)
    
    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message}
