from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status

import schemas
from database import get_db, MovieModel
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas.movies import MovieCreateSchema, MessageSchema, MovieUpdateSchema

router = APIRouter()


async def get_or_create(
    model: type[Any], name: str, db: AsyncSession = Depends(get_db)
) -> Any:
    get_object = await db.execute(select(model).where(model.name == name))
    entity = get_object.scalar_one_or_none()
    if entity is None:
        entity = model(name=name)
        db.add(entity)
    return entity


@router.get("/movies/{movie_id}/", response_model=schemas.movies.MovieDetailSchema)
async def get_film_by_id(
    movie_id: int, db: AsyncSession = Depends(get_db)
) -> MovieModel:
    result = await db.execute(
        select(MovieModel)
        .options(
            joinedload(MovieModel.country),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
        )
        .where(MovieModel.id == movie_id)
    )
    movie = result.unique().scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )
    return movie


@router.delete("/movies/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_film_by_id(movie_id: int, db: AsyncSession = Depends(get_db)):
    movie = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = movie.scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404, detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()


@router.post(
    "/movies/",
    response_model=schemas.movies.MovieDetailSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_movie(
    movie: MovieCreateSchema, db: AsyncSession = Depends(get_db)
) -> MovieModel:
    check_duplicate = await db.execute(
        select(MovieModel).where(
            MovieModel.name == movie.name, MovieModel.date == movie.date
        )
    )

    if check_duplicate.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie.name}' "
            f"and release date '{movie.date}' already exists.",
        )

    country = await db.execute(
        select(CountryModel).where(CountryModel.code == movie.country)
    )
    country = country.scalar_one_or_none()
    if country is None:
        country = CountryModel(code=movie.country)
        db.add(country)

    genres = [await get_or_create(GenreModel, name, db) for name in movie.genres]

    actors = [await get_or_create(ActorModel, name, db) for name in movie.actors]

    languages = [
        await get_or_create(LanguageModel, name, db) for name in movie.languages
    ]

    movie_fields = movie.model_dump(
        exclude={"country", "genres", "actors", "languages"}
    )

    validated_movie = MovieModel(
        **movie_fields,
        country=country,
        genres=genres,
        actors=actors,
        languages=languages,
    )

    db.add(validated_movie)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                f"A movie with the name '{movie.name}' and release date "
                f"'{movie.date}' already exists."
            ),
        )

    return validated_movie


@router.get("/movies/", response_model=schemas.movies.MovieListResponseSchema)
async def get_film(
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> list[MovieModel]:
    total_items = await db.scalar(select(func.count()).select_from(MovieModel))
    total_items = total_items or 0
    total_pages = (total_items + per_page - 1) // per_page

    movies = await db.execute(
        select(MovieModel)
        .order_by(-MovieModel.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    movies = list(movies.scalars().all())

    if not movies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No movies found.",
        )

    return schemas.movies.MovieListResponseSchema(
        movies=movies,
        prev_page=(
            f"/theater/movies/?page={page - 1}&per_page={per_page}"
            if page > 1
            else None
        ),
        next_page=(
            f"/theater/movies/?page={page + 1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


@router.patch("/movies/{movie_id}/", response_model=MessageSchema)
async def update_movie(
    movie_id: int, movie: MovieUpdateSchema, db: AsyncSession = Depends(get_db)
) -> MovieModel:
    get_movie = await db.get(MovieModel, movie_id)

    if get_movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )

    for field_name, value in movie.model_dump(exclude_unset=True).items():
        setattr(get_movie, field_name, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return MessageSchema(detail="Movie updated successfully.")
