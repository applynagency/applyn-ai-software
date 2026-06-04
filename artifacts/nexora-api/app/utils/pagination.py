from pydantic import BaseModel


class PaginationParams(BaseModel):
    offset: int = 0
    limit: int = 50

    @property
    def page(self) -> int:
        return self.offset // self.limit + 1
