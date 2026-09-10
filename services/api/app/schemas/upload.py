import uuid

from pydantic import BaseModel, Field


class UploadCreate(BaseModel):
    filename: str = Field(
        min_length=1,
        max_length=255,
    )

    content_type: str = Field(
        min_length=1,
        max_length=127,
    )

    size_bytes: int = Field(
        gt=0,
    )


class UploadPartURL(BaseModel):
    part_number: int
    url: str


class UploadInitiateResponse(BaseModel):
    upload_id: uuid.UUID

    object_key: str

    part_size_bytes: int
    part_count: int

    parts: list[UploadPartURL]


class CompletedPart(BaseModel):
    part_number: int = Field(
        ge=1,
    )

    etag: str = Field(
        min_length=1,
    )


class UploadCompleteRequest(BaseModel):
    parts: list[CompletedPart]