from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel
from pydantic.generics import GenericModel


T = TypeVar("T")


class ApiResponse(GenericModel, Generic[T]):
    code: int
    message: str
    data: Optional[T] = None


class ValidationErrorItem(BaseModel):
    loc: List[Any]
    msg: str
    type: str


class ErrorResponse(ApiResponse[T], Generic[T]):
    pass


class PaginatedData(GenericModel, Generic[T]):
    total: int
    page: int
    size: int
    totalPages: int
    items: List[T]


def api_response(code: int, message: str, data: Optional[T] = None) -> ApiResponse[T]:
    return ApiResponse[T](code=code, message=message, data=data)


def success_response(data: Optional[T] = None, message: str = "success") -> ApiResponse[T]:
    return api_response(200, message, data)


def created_response(data: Optional[T] = None, message: str = "created") -> ApiResponse[T]:
    return api_response(201, message, data)


def error_response(code: int, message: str, data: Optional[T] = None) -> ErrorResponse[T]:
    return ErrorResponse[T](code=code, message=message, data=data)


def paginated_response(items: List[T], total: int, page: int, size: int, message: str = "success") -> ApiResponse[PaginatedData[T]]:
    total_pages = (total + size - 1) // size if size > 0 else 0
    page_data = PaginatedData[T](
        total=total,
        page=page,
        size=size,
        totalPages=total_pages,
        items=items,
    )
    return success_response(page_data, message=message)

