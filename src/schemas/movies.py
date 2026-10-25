import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from database.models import MovieStatusEnum


class ORMModelSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NamedSchema(ORMModelSchema):
    id: int
    name: str


class LanguageSchema(NamedSchema):
    pass


class GenreSchema(NamedSchema):
    pass


class ActorSchema(NamedSchema):
    pass


class CountrySchema(ORMModelSchema):
    id: int
    code: str
    name: str | None


class MovieListItemSchema(ORMModelSchema):
    id: int
    name: str
    date: datetime.date
    score: float
    overview: str


class MovieDetailSchema(MovieListItemSchema):
    status: str
    budget: float
    revenue: float
    country: CountrySchema
    genres: list[GenreSchema]
    actors: list[ActorSchema]
    languages: list[LanguageSchema]


class MovieListResponseSchema(ORMModelSchema):
    movies: list[MovieListItemSchema]
    prev_page: str | None
    next_page: str | None
    total_pages: int
    total_items: int


class MovieDataSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    date: datetime.date
    score: float = Field(ge=0, le=100)
    overview: str
    budget: float = Field(ge=0)
    revenue: float = Field(ge=0)
    status: MovieStatusEnum

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: datetime.date):
        if value > datetime.date.today() + datetime.timedelta(days=365):
            raise ValueError("Date must not be more than one year in the future.")
        return value


class MovieCreateSchema(MovieDataSchema):
    country: str = Field(min_length=2, max_length=3)
    genres: list[str]
    actors: list[str]
    languages: list[str]

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, value: str):
        return value.upper()

    @field_validator("genres", "actors", "languages")
    @classmethod
    def validate_names(cls, values: list[str]):
        if any(not value or len(value) > 255 for value in values):
            raise ValueError("Names must be between 1 and 255 characters.")

        return list(dict.fromkeys(values))


class MovieUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    date: datetime.date | None = None
    score: float = Field(default=None, ge=0, le=100)
    overview: str | None = None
    budget: float = Field(default=None, ge=0)
    revenue: float = Field(default=None, ge=0)
    status: MovieStatusEnum | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: datetime.date):
        if value > datetime.date.today() + datetime.timedelta(days=365):
            raise ValueError("Date must not be more than one year in the future.")
        return value

    @model_validator(mode="after")
    def reject_nulls(self):
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"Field '{field_name}' can't be null.")
        return self


class MessageSchema(BaseModel):
    detail: str
